# pyright: basic
'''
Its gonna be a connector between - Python -> Azure Video indexer
'''
import os
import logging
import time
import requests
import yt_dlp

from azure.identity import DefaultAzureCredential

logger = logging.getLogger("video-indexer")

class VideoIndexerService:
    def __init__(self):
        self.account_id = os.getenv("AZURE_VI_ACCOUNT_ID")
        self.location = os.getenv("AZURE_VI_LOCATION")
        self.subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
        self.resource_group = os.getenv("AZURE_RESOURCE_GROUP")
        self.vi_name = os.getenv("AZURE_VI_NAME", "brand-comliance-video")
        self.credential = DefaultAzureCredential()
        
    def get_access_token(self):
        # Generates the ARM Access Token
        try:
            token_object = self.credential.get_token("https://management.azure.com/.default")
            return token_object.token
        except Exception as e:
            logger.error(f"Failed to get Azure Token: {e}")
            raise
        
    def get_account_token(self, arm_access_token):
        #Exchanges ARM token for Video Indexer Account Token.
        url = (
            f"https://management.azure.com/subscriptions/{self.subscription_id}"
            f"/resourceGroups/{self.resource_group}"
            f"/providers/Microsoft.VideoIndexer/accounts/{self.vi_name}"
            f"/generateAccessToken?api-version=2024-01-01"
        )
        headers = {"Authorization": f"Bearer {arm_access_token}"}
        payload = {"permissionType": "Contributor", "scope": "Account"}
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            raise Exception(f"Failed to get VI Account Token: {response.text}")
        return response.json().get("accessToken")
    
    # Download the Youtube video
    def download_youtube_video(self, url, output_path="temp_video.mp4"):
        '''Downloads the yt video using RapidAPI YTStream'''
        logger.info(f"Downloading youtube video: {url}")

        # Extract video ID from URL
        if "youtu.be/" in url:
            video_id = url.split("youtu.be/")[-1].split("?")[0]
        else:
            video_id = url.split("v=")[-1].split("&")[0]

        api_url = "https://ytstream-download-youtube-videos.p.rapidapi.com/dl"
        headers = {
            "x-rapidapi-key": os.getenv("RAPIDAPI_KEY"),
            "x-rapidapi-host": "ytstream-download-youtube-videos.p.rapidapi.com"
        }
        api_key = os.getenv("RAPIDAPI_KEY")
        logger.info(f"RapidAPI key length: {len(api_key) if api_key else 'NOT SET'}")
        response = requests.get(api_url, headers=headers, params={"id": video_id})
        data = response.json()

        # Get lowest quality mp4 (enough for Azure VI)
        formats = data.get("formats", {})
        mp4_url = None
        for quality in ["360", "240", "480", "720"]:
            if quality in formats:
                mp4_url = formats[quality]["url"]
                break

        if not mp4_url:
            raise Exception(f"No MP4 format available. API response: {data}")
        
        

        # Stream download to file
        video_response = requests.get(mp4_url, stream=True)
        with open(output_path, "wb") as f:
            for chunk in video_response.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info("Download complete!!!")
        return output_path
        
    
    # Upload to downloaded to Azure Video Indexer
    def upload_video(self, video_path, video_name):
        arm_token = self.get_access_token()
        vi_token = self.get_account_token(arm_token)
        
        api_url = f"https://api.videoindexer.ai/{self.location}/Accounts/{self.account_id}/Videos"
        
        params = {
            "accessToken" : vi_token,
            "name" : video_name,
            "privacy" : "Private",
            "IndexingPreset" : "Default"
        }
        
        logger.info(f"Uploading the file {video_path} to Azure...")
        
        # Open the file in read binary mode and stream it to Azure
        with open(video_path,'rb') as video_file:
            files = {'file':video_file}
            response = requests.post(api_url, params=params, files=files)
            
        if response.status_code != 200:
            raise Exception(f"Azure Upload Failed: {response.text}")
            
        return response.json().get("id")
    
    def wait_for_processing(self, video_id):
        logger.info(f"Waiting for the video {video_id} to process...")
        while True:
            arm_token = self.get_access_token()
            vi_token = self.get_account_token(arm_token)
            
            url = f"https://api.videoindexer.ai/{self.location}/Accounts/{self.account_id}/Videos/{video_id}/Index"
            params = {"accessToken" : vi_token}
            response = requests.get(url, params=params)
            data = response.json()
            
            state = data.get("state")
            if state == "Processed":
                return data
            elif state == "Failed":
                raise Exception("Video Indexing Failed in Azure.")
            elif state == "Quarantined":
                raise Exception("Video Quarantined (Copyright/Content Policy Violation).")
        
            logger.info(f"Status: {state}... waiting 30s")
            time.sleep(30)
            
    def extract_data(self, vi_json):
        '''Parses the JSON into state format'''
        logger.info(f"VI JSON keys: {list(vi_json.keys())}")
        videos = vi_json.get("videos", [])
        logger.info(f"Number of videos: {len(videos)}")
        if videos:
            insights = videos[0].get("insights", {})
            logger.info(f"Insights keys: {list(insights.keys())}")
            logger.info(f"Transcript sample: {insights.get('transcript', [])[:2]}")

        transcript_lines = []
        for v in vi_json.get("videos", []):
            for insights in v.get("insights",{}).get("transcript",[]):
                transcript_lines.append(insights.get("text"))    
        
        ocr_lines = []
        for v in vi_json.get("videos",[]):
            for insights in v.get("insights",{}).get("ocr",[]):
                ocr_lines.append(insights.get("text"))
        return {
            "transcript" : " ".join(transcript_lines),
            "ocr_text" : ocr_lines,
            "video_metadata": {
                "duration" : vi_json.get("summarizedInsights", {}).get("duration"),
                "platform" : "youtube"
            }
        }
        