import json
from moviepy.editor import *
from deepgram import (
    DeepgramClient,
    SpeakOptions,
)
import asyncio
import os
from pathlib import Path
import aiohttp
import aiofiles
import numpy as np
from PIL import Image
from dotenv import load_dotenv
import re
from pydub import AudioSegment

load_dotenv()

async def generate_audio(text, scene_title):
    """Generate audio file from text using Deepgram"""
    DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
    if not DEEPGRAM_API_KEY:
        raise ValueError("DEEPGRAM_API_KEY environment variable not set")
    
    # Skip if text is empty
    if not text or text.strip() == "":
        print(f"    >>Skipping audio generation for {scene_title}: Empty text")
        return None
    
    try:
        # Initialize audio files list
        audio_files = []
        
        # Split text into chunks at sentence boundaries
        chunks = split_into_chunks(text)
        print(f"    >>Split text into {len(chunks)} chunks for {scene_title}")
        
        for i, chunk in enumerate(chunks):
            temp_audio_file = f"temp_audio_{scene_title.replace(' ', '_')}_{i}.mp3"
            print(f"    >>Generating audio for chunk {i+1}/{len(chunks)}")
            
            # Create Deepgram client
            deepgram = DeepgramClient()
            
            # Configure TTS options
            speak_text = {"text": chunk}
            options = SpeakOptions(
                model="aura-asteria-en",
            )
            
            # Generate and save audio
            response = await deepgram.speak.asyncrest.v("1").save(temp_audio_file, speak_text, options)
            
            if os.path.exists(temp_audio_file):
                # Convert MP3 to WAV using pydub
                try:
                    audio = AudioSegment.from_file(temp_audio_file, format="mp3")
                    wav_file = temp_audio_file.replace('.mp3', '.wav')
                    audio.export(wav_file, format="wav")
                    audio_files.append(wav_file)
                    os.remove(temp_audio_file)  # Clean up MP3 file
                except Exception as e:
                    print(f"    >>Error converting audio for chunk {i+1}: {e}")
                    continue
            else:
                print(f"    >>No audio file created for chunk {i+1}")
        
        if not audio_files:
            print(f"    >>No audio files created for {scene_title}")
            return None
            
        # If we have multiple chunks, concatenate them
        if len(audio_files) > 1:
            final_audio = f"audio_{scene_title.replace(' ', '_')}.wav"
            concatenate_audio_files(audio_files, final_audio)
            
            # Clean up temporary files
            for temp_file in audio_files:
                os.remove(temp_file)
                
            return final_audio
        else:
            # If only one chunk, just return that file
            return audio_files[0]
            
    except Exception as e:
        print(f"    >>Error generating audio for {scene_title}: {e}")
        # Clean up any temporary files that might have been created
        for temp_file in audio_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        return None

def split_into_chunks(text, max_chars=1900):  # Using 1900 to leave some buffer
    """Split text into chunks at sentence boundaries while respecting character limit"""
    # First split into sentences
    sentences = re.split('(?<=[.!?])\s+', text)
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        # If adding this sentence would exceed the limit, start a new chunk
        if len(current_chunk) + len(sentence) > max_chars:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence
        else:
            current_chunk = current_chunk + " " + sentence if current_chunk else sentence
    
    # Add the last chunk if it exists
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

def concatenate_audio_files(audio_files, output_file):
    """Concatenate multiple audio files into one"""
    combined = AudioSegment.empty()
    for audio_file in audio_files:
        segment = AudioSegment.from_wav(audio_file)
        combined += segment
    combined.export(output_file, format="wav")

def resize_image(image_path, target_size=(1920, 1080)):
    """Resize image to target size while maintaining aspect ratio"""
    img = Image.open(image_path)
    img_ratio = img.size[0] / img.size[1]
    target_ratio = target_size[0] / target_size[1]
    
    if img_ratio > target_ratio:
        # Image is wider than target
        new_width = target_size[0]
        new_height = int(new_width / img_ratio)
    else:
        # Image is taller than target
        new_height = target_size[1]
        new_width = int(new_height * img_ratio)
    
    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Create new image with black background
    new_img = Image.new('RGB', target_size, (0, 0, 0))
    # Paste resized image in center
    x = (target_size[0] - new_width) // 2
    y = (target_size[1] - new_height) // 2
    new_img.paste(img, (x, y))
    
    # Save and return path
    output_path = f"resized_{Path(image_path).name}"
    new_img.save(output_path)
    return output_path

async def create_scene_clip(scene):
    """Create video clip for a single scene"""
    # Generate audio for scene text
    audio_file = await generate_audio(scene['text'], scene['title'])
    if not audio_file:
        return None
    
    # Load and resize image
    resized_image = resize_image(scene['visual_path'])
    
    # Create video clip
    audio = AudioFileClip(audio_file)
    image = ImageClip(resized_image)
    
    # Set duration to match audio
    video = image.set_duration(audio.duration)
    
    # Combine audio and video
    final_clip = video.set_audio(audio)
    
    # Clean up temporary files
    os.remove(audio_file)
    os.remove(resized_image)
    
    return final_clip

async def create_video(scenes_file, output_file):
    """Create complete video from all scenes"""
    # Load scenes
    with open(scenes_file, 'r') as f:
        scenes = json.load(f)
    
    print(f"\nTotal scenes found: {len(scenes)}")
    
    # Create clip for each scene
    clips = []
    for i, scene in enumerate(scenes):
        print(f"\nProcessing scene {i+1}/{len(scenes)}: {scene['title']}")
        
        if not scene.get('visual_path'):
            print(f"    Skipping scene {scene['title']}: No visual path")
            continue
            
        if not scene.get('text'):
            print(f"    Skipping scene {scene['title']}: No text")
            continue
            
        if not os.path.exists(scene['visual_path']):
            print(f"    Skipping scene {scene['title']}: Image file not found at {scene['visual_path']}")
            continue
        
        print(f"    Creating clip for scene {scene['title']}")
        clip = await create_scene_clip(scene)
        if clip:
            clips.append(clip)
            print(f"    Successfully created clip for {scene['title']}")
        else:
            print(f"    Failed to create clip for {scene['title']}")
    
    print(f"\nTotal clips created: {len(clips)}")
    
    if not clips:
        raise ValueError("No valid clips were created")
    
    # Concatenate all clips
    print("\nConcatenating clips...")
    final_video = concatenate_videoclips(clips)
    
    # Write final video
    print("\nWriting final video...")
    final_video.write_videofile(
        output_file,
        fps=24,
        codec='libx264',
        audio_codec='aac'
    )
    
    # Clean up clips
    for clip in clips:
        clip.close()

if __name__ == "__main__":
    scenes_file = "complete_scenes.json"
    output_file = "textbook_video.mp4"
    
    try:
        asyncio.run(create_video(scenes_file, output_file))
        print(f"Video successfully created: {output_file}")
    except Exception as e:
        print(f"Error creating video: {e}") 