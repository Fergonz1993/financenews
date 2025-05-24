#!/usr/bin/env python3
"""
Multimodal Financial Sentiment Analyzer
Advanced AI system for analyzing sentiment across text, audio, video, and visual modalities.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Union, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import tempfile
import io
import base64
from datetime import datetime
import json

# Core processing libraries
import numpy as np
import pandas as pd
import cv2
from PIL import Image, ImageDraw, ImageFont
import librosa
import speech_recognition as sr
from moviepy.editor import VideoFileClip
import matplotlib.pyplot as plt
import seaborn as sns

# AI and ML libraries
import torch
import torch.nn as nn
import torch.nn.functional as F
import transformers
from transformers import (
    AutoTokenizer, AutoModel, AutoProcessor,
    Wav2Vec2ForSequenceClassification, Wav2Vec2Processor,
    CLIPModel, CLIPProcessor,
    pipeline
)
import whisper
from sentence_transformers import SentenceTransformer
import openai
from openai import AsyncOpenAI

# Web scraping and media processing
import yt_dlp
import requests
import aiohttp
import aiofiles

# Async processing
from concurrent.futures import ThreadPoolExecutor
import asyncio
from asyncio_throttle import Throttler

logger = logging.getLogger(__name__)

@dataclass
class MultimodalSentimentResult:
    """Result from multimodal sentiment analysis."""
    
    # Overall results
    overall_sentiment: float  # -1 to 1
    confidence: float        # 0 to 1
    modality_weights: Dict[str, float]
    
    # Individual modality results
    text_sentiment: Optional[float] = None
    audio_sentiment: Optional[float] = None
    visual_sentiment: Optional[float] = None
    facial_sentiment: Optional[float] = None
    
    # Detailed analysis
    emotions: Dict[str, float] = None
    key_phrases: List[str] = None
    transcription: Optional[str] = None
    visual_features: Dict[str, Any] = None
    
    # Metadata
    processing_time: float = 0.0
    source_type: str = "unknown"
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.emotions is None:
            self.emotions = {}
        if self.key_phrases is None:
            self.key_phrases = []
        if self.visual_features is None:
            self.visual_features = {}
        if self.timestamp is None:
            self.timestamp = datetime.now()

class AdvancedTextSentimentAnalyzer:
    """Enhanced text sentiment analysis with financial domain knowledge."""
    
    def __init__(self):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Load financial-specific models
        self.tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
        self.finbert_model = AutoModel.from_pretrained("ProsusAI/finbert").to(self.device)
        
        # General sentiment pipeline
        self.sentiment_pipeline = pipeline(
            "sentiment-analysis",
            model="cardiffnlp/twitter-roberta-base-sentiment-latest",
            device=0 if torch.cuda.is_available() else -1
        )
        
        # Emotion detection
        self.emotion_pipeline = pipeline(
            "text-classification",
            model="j-hartmann/emotion-english-distilroberta-base",
            device=0 if torch.cuda.is_available() else -1
        )
        
        # Financial keywords and patterns
        self.financial_keywords = {
            'positive': ['beat', 'exceed', 'strong', 'growth', 'bullish', 'optimistic', 'upgrade'],
            'negative': ['miss', 'decline', 'weak', 'bearish', 'pessimistic', 'downgrade', 'concern'],
            'uncertainty': ['volatile', 'uncertain', 'cautious', 'mixed', 'challenging']
        }
    
    async def analyze_text(self, text: str, context: str = "financial") -> Dict[str, Any]:
        """Comprehensive text sentiment analysis."""
        
        start_time = asyncio.get_event_loop().time()
        
        # Basic sentiment analysis
        basic_sentiment = await self._get_basic_sentiment(text)
        
        # Financial-specific analysis
        financial_sentiment = await self._get_financial_sentiment(text)
        
        # Emotion analysis
        emotions = await self._get_emotions(text)
        
        # Key phrase extraction
        key_phrases = await self._extract_key_phrases(text)
        
        # Confidence calculation
        confidence = self._calculate_text_confidence(basic_sentiment, financial_sentiment, emotions)
        
        # Final sentiment score (weighted combination)
        final_sentiment = (
            basic_sentiment['score'] * 0.4 +
            financial_sentiment * 0.5 +
            (emotions.get('joy', 0) - emotions.get('sadness', 0)) * 0.1
        )
        
        processing_time = asyncio.get_event_loop().time() - start_time
        
        return {
            'sentiment_score': final_sentiment,
            'confidence': confidence,
            'basic_sentiment': basic_sentiment,
            'financial_sentiment': financial_sentiment,
            'emotions': emotions,
            'key_phrases': key_phrases,
            'processing_time': processing_time
        }
    
    async def _get_basic_sentiment(self, text: str) -> Dict[str, float]:
        """Get basic sentiment using RoBERTa model."""
        
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, self.sentiment_pipeline, text)
        
        # Convert to normalized score
        label = result[0]['label'].lower()
        score = result[0]['score']
        
        if 'positive' in label:
            normalized_score = score
        elif 'negative' in label:
            normalized_score = -score
        else:  # neutral
            normalized_score = 0.0
        
        return {'score': normalized_score, 'confidence': score, 'label': label}
    
    async def _get_financial_sentiment(self, text: str) -> float:
        """Get financial-specific sentiment using FinBERT."""
        
        # Tokenize and process with FinBERT
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, 
                               padding=True, max_length=512).to(self.device)
        
        with torch.no_grad():
            outputs = self.finbert_model(**inputs)
            embeddings = outputs.last_hidden_state.mean(dim=1)
        
        # Simple financial sentiment calculation
        # This is a simplified approach - in practice, you'd want a fine-tuned classifier
        financial_score = 0.0
        
        text_lower = text.lower()
        for sentiment_type, keywords in self.financial_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    if sentiment_type == 'positive':
                        financial_score += 0.1
                    elif sentiment_type == 'negative':
                        financial_score -= 0.1
                    elif sentiment_type == 'uncertainty':
                        financial_score -= 0.05
        
        return np.tanh(financial_score)  # Normalize to [-1, 1]
    
    async def _get_emotions(self, text: str) -> Dict[str, float]:
        """Extract emotional content from text."""
        
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            results = await loop.run_in_executor(executor, self.emotion_pipeline, text)
        
        emotions = {}
        for result in results:
            emotion = result['label'].lower()
            score = result['score']
            emotions[emotion] = score
        
        return emotions
    
    async def _extract_key_phrases(self, text: str) -> List[str]:
        """Extract key financial phrases from text."""
        
        # Simple keyword extraction - could be enhanced with NER or topic modeling
        financial_terms = [
            'earnings', 'revenue', 'profit', 'loss', 'guidance', 'outlook',
            'market share', 'competition', 'regulation', 'acquisition',
            'dividend', 'buyback', 'expansion', 'margin', 'growth'
        ]
        
        text_lower = text.lower()
        found_phrases = []
        
        for term in financial_terms:
            if term in text_lower:
                found_phrases.append(term)
        
        return found_phrases
    
    def _calculate_text_confidence(self, basic_sentiment: Dict, 
                                 financial_sentiment: float, 
                                 emotions: Dict) -> float:
        """Calculate confidence in text sentiment analysis."""
        
        # Combine multiple confidence indicators
        basic_confidence = basic_sentiment['confidence']
        emotion_confidence = max(emotions.values()) if emotions else 0.0
        
        # Agreement between models increases confidence
        sentiment_agreement = 1.0 - abs(basic_sentiment['score'] - financial_sentiment)
        
        return np.mean([basic_confidence, emotion_confidence, sentiment_agreement])

class AudioSentimentAnalyzer:
    """Advanced audio sentiment analysis for earnings calls and interviews."""
    
    def __init__(self):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Load speech emotion recognition model
        self.processor = Wav2Vec2Processor.from_pretrained("facebook/wav2vec2-base-960h")
        
        # Whisper for transcription
        self.whisper_model = whisper.load_model("base")
        
        # Speech recognition for backup
        self.speech_recognizer = sr.Recognizer()
        
    async def analyze_audio(self, audio_path: str) -> Dict[str, Any]:
        """Comprehensive audio sentiment analysis."""
        
        start_time = asyncio.get_event_loop().time()
        
        # Load audio file
        audio_data, sample_rate = librosa.load(audio_path, sr=16000)
        
        # Extract acoustic features
        acoustic_features = await self._extract_acoustic_features(audio_data, sample_rate)
        
        # Transcribe audio
        transcription = await self._transcribe_audio(audio_path)
        
        # Analyze speech patterns
        speech_patterns = await self._analyze_speech_patterns(audio_data, sample_rate)
        
        # Calculate sentiment from acoustic features
        acoustic_sentiment = self._calculate_acoustic_sentiment(acoustic_features)
        
        # Calculate confidence
        confidence = self._calculate_audio_confidence(acoustic_features, speech_patterns)
        
        processing_time = asyncio.get_event_loop().time() - start_time
        
        return {
            'sentiment_score': acoustic_sentiment,
            'confidence': confidence,
            'transcription': transcription,
            'acoustic_features': acoustic_features,
            'speech_patterns': speech_patterns,
            'processing_time': processing_time
        }
    
    async def _extract_acoustic_features(self, audio_data: np.ndarray, 
                                       sample_rate: int) -> Dict[str, float]:
        """Extract acoustic features relevant to emotion and sentiment."""
        
        features = {}
        
        # Fundamental frequency (pitch)
        pitches, magnitudes = librosa.piptrack(y=audio_data, sr=sample_rate)
        pitch_mean = np.mean(pitches[pitches > 0]) if np.any(pitches > 0) else 0
        pitch_std = np.std(pitches[pitches > 0]) if np.any(pitches > 0) else 0
        
        features['pitch_mean'] = float(pitch_mean)
        features['pitch_std'] = float(pitch_std)
        
        # Spectral features
        spectral_centroids = librosa.feature.spectral_centroid(y=audio_data, sr=sample_rate)[0]
        features['spectral_centroid_mean'] = float(np.mean(spectral_centroids))
        features['spectral_centroid_std'] = float(np.std(spectral_centroids))
        
        # Zero crossing rate (voice activity)
        zcr = librosa.feature.zero_crossing_rate(audio_data)[0]
        features['zcr_mean'] = float(np.mean(zcr))
        
        # MFCC features
        mfccs = librosa.feature.mfcc(y=audio_data, sr=sample_rate, n_mfcc=13)
        for i in range(13):
            features[f'mfcc_{i}_mean'] = float(np.mean(mfccs[i]))
            features[f'mfcc_{i}_std'] = float(np.std(mfccs[i]))
        
        # Energy features
        rms = librosa.feature.rms(y=audio_data)[0]
        features['energy_mean'] = float(np.mean(rms))
        features['energy_std'] = float(np.std(rms))
        
        return features
    
    async def _transcribe_audio(self, audio_path: str) -> str:
        """Transcribe audio to text using Whisper."""
        
        try:
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(
                    executor, 
                    self.whisper_model.transcribe, 
                    audio_path
                )
            
            return result["text"]
        
        except Exception as e:
            logger.warning(f"Whisper transcription failed: {e}")
            return ""
    
    async def _analyze_speech_patterns(self, audio_data: np.ndarray, 
                                     sample_rate: int) -> Dict[str, Any]:
        """Analyze speech patterns for emotional indicators."""
        
        patterns = {}
        
        # Speaking rate
        onset_frames = librosa.onset.onset_detect(y=audio_data, sr=sample_rate)
        speaking_rate = len(onset_frames) / (len(audio_data) / sample_rate)
        patterns['speaking_rate'] = float(speaking_rate)
        
        # Pause analysis
        rms = librosa.feature.rms(y=audio_data)[0]
        silence_threshold = np.percentile(rms, 20)
        pauses = rms < silence_threshold
        pause_count = np.sum(np.diff(pauses.astype(int)) == 1)
        patterns['pause_count'] = int(pause_count)
        
        # Voice quality indicators
        # Jitter (pitch variability)
        pitches, _ = librosa.piptrack(y=audio_data, sr=sample_rate)
        valid_pitches = pitches[pitches > 0]
        if len(valid_pitches) > 1:
            jitter = np.std(np.diff(valid_pitches)) / np.mean(valid_pitches)
            patterns['jitter'] = float(jitter)
        else:
            patterns['jitter'] = 0.0
        
        return patterns
    
    def _calculate_acoustic_sentiment(self, features: Dict[str, float]) -> float:
        """Calculate sentiment score from acoustic features."""
        
        # This is a simplified heuristic-based approach
        # In practice, you'd want a trained model
        
        sentiment_score = 0.0
        
        # Higher pitch often indicates stress or excitement
        if features['pitch_mean'] > 200:  # High pitch
            if features['pitch_std'] > 50:  # High variability
                sentiment_score -= 0.2  # Stress/anxiety
            else:
                sentiment_score += 0.1   # Excitement
        elif features['pitch_mean'] < 100:  # Low pitch
            sentiment_score -= 0.1  # Potentially negative
        
        # Speaking rate indicators
        if features.get('speaking_rate', 0) > 5:  # Fast speaking
            sentiment_score -= 0.1  # Potential stress
        elif features.get('speaking_rate', 0) < 2:  # Slow speaking
            sentiment_score -= 0.1  # Potential sadness/depression
        
        # Energy levels
        if features['energy_mean'] > 0.1:
            sentiment_score += 0.1  # High energy positive
        elif features['energy_mean'] < 0.05:
            sentiment_score -= 0.1  # Low energy negative
        
        return np.tanh(sentiment_score)  # Normalize to [-1, 1]
    
    def _calculate_audio_confidence(self, features: Dict[str, float], 
                                  patterns: Dict[str, Any]) -> float:
        """Calculate confidence in audio sentiment analysis."""
        
        # Confidence based on audio quality and feature reliability
        confidence = 0.5  # Base confidence
        
        # Good energy signal increases confidence
        if features['energy_mean'] > 0.05:
            confidence += 0.2
        
        # Clear pitch detection increases confidence
        if features['pitch_mean'] > 50:
            confidence += 0.2
        
        # Consistent patterns increase confidence
        if features['pitch_std'] < 100:  # Stable pitch
            confidence += 0.1
        
        return min(confidence, 1.0)

class VisualSentimentAnalyzer:
    """Advanced visual sentiment analysis for presentations and videos."""
    
    def __init__(self):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Load CLIP for image understanding
        self.clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        self.clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        
        # Face detection
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        
        # Sentiment-related text prompts for CLIP
        self.sentiment_prompts = [
            "a confident business person",
            "a worried executive",
            "a happy presenter",
            "a serious meeting",
            "positive financial charts",
            "negative financial data",
            "professional presentation",
            "casual discussion"
        ]
    
    async def analyze_image(self, image_path: str) -> Dict[str, Any]:
        """Comprehensive visual sentiment analysis."""
        
        start_time = asyncio.get_event_loop().time()
        
        # Load image
        image = Image.open(image_path).convert('RGB')
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # Face detection and analysis
        face_analysis = await self._analyze_faces(cv_image)
        
        # CLIP-based scene understanding
        scene_analysis = await self._analyze_scene(image)
        
        # Color and composition analysis
        visual_features = await self._analyze_visual_features(image)
        
        # Calculate overall visual sentiment
        visual_sentiment = self._calculate_visual_sentiment(
            face_analysis, scene_analysis, visual_features
        )
        
        # Calculate confidence
        confidence = self._calculate_visual_confidence(
            face_analysis, scene_analysis, visual_features
        )
        
        processing_time = asyncio.get_event_loop().time() - start_time
        
        return {
            'sentiment_score': visual_sentiment,
            'confidence': confidence,
            'face_analysis': face_analysis,
            'scene_analysis': scene_analysis,
            'visual_features': visual_features,
            'processing_time': processing_time
        }
    
    async def _analyze_faces(self, cv_image: np.ndarray) -> Dict[str, Any]:
        """Analyze facial expressions and emotions."""
        
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
        
        face_data = {
            'face_count': len(faces),
            'faces': [],
            'average_sentiment': 0.0
        }
        
        if len(faces) == 0:
            return face_data
        
        # Analyze each detected face
        sentiments = []
        for (x, y, w, h) in faces:
            face_roi = cv_image[y:y+h, x:x+w]
            
            # Simple heuristic-based facial analysis
            # In practice, you'd use a dedicated facial emotion recognition model
            face_sentiment = self._analyze_single_face(face_roi)
            
            face_data['faces'].append({
                'position': [int(x), int(y), int(w), int(h)],
                'sentiment': face_sentiment
            })
            sentiments.append(face_sentiment)
        
        face_data['average_sentiment'] = float(np.mean(sentiments))
        return face_data
    
    def _analyze_single_face(self, face_roi: np.ndarray) -> float:
        """Analyze sentiment of a single face region."""
        
        # This is a simplified placeholder
        # In practice, you'd use a trained facial emotion recognition model
        
        # Basic brightness and contrast analysis as a proxy
        gray_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        brightness = np.mean(gray_face)
        contrast = np.std(gray_face)
        
        # Simple heuristic: brighter faces with good contrast might indicate positivity
        sentiment = (brightness - 100) / 100 + (contrast - 50) / 50
        return np.tanh(sentiment * 0.1)  # Very conservative scoring
    
    async def _analyze_scene(self, image: Image.Image) -> Dict[str, Any]:
        """Analyze the overall scene using CLIP."""
        
        # Prepare inputs
        inputs = self.clip_processor(
            text=self.sentiment_prompts, 
            images=image, 
            return_tensors="pt", 
            padding=True
        )
        
        # Get CLIP predictions
        with torch.no_grad():
            outputs = self.clip_model(**inputs)
            logits_per_image = outputs.logits_per_image
            probs = logits_per_image.softmax(dim=1)
        
        # Map probabilities to sentiment prompts
        scene_analysis = {}
        for i, prompt in enumerate(self.sentiment_prompts):
            scene_analysis[prompt] = float(probs[0][i])
        
        # Calculate overall scene sentiment
        positive_prompts = [
            "a confident business person",
            "a happy presenter", 
            "positive financial charts",
            "professional presentation"
        ]
        
        negative_prompts = [
            "a worried executive",
            "negative financial data"
        ]
        
        positive_score = sum(scene_analysis[p] for p in positive_prompts)
        negative_score = sum(scene_analysis[p] for p in negative_prompts)
        
        scene_sentiment = positive_score - negative_score
        scene_analysis['overall_sentiment'] = float(scene_sentiment)
        
        return scene_analysis
    
    async def _analyze_visual_features(self, image: Image.Image) -> Dict[str, Any]:
        """Analyze color, composition, and other visual features."""
        
        # Convert to numpy array
        img_array = np.array(image)
        
        features = {}
        
        # Color analysis
        avg_color = np.mean(img_array, axis=(0, 1))
        features['avg_red'] = float(avg_color[0])
        features['avg_green'] = float(avg_color[1])
        features['avg_blue'] = float(avg_color[2])
        
        # Brightness and contrast
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        features['brightness'] = float(np.mean(gray))
        features['contrast'] = float(np.std(gray))
        
        # Color diversity (using histogram)
        hist_r = cv2.calcHist([img_array], [0], None, [256], [0, 256])
        hist_g = cv2.calcHist([img_array], [1], None, [256], [0, 256])
        hist_b = cv2.calcHist([img_array], [2], None, [256], [0, 256])
        
        features['color_diversity'] = float(
            np.std(hist_r) + np.std(hist_g) + np.std(hist_b)
        )
        
        # Edge density (activity in image)
        edges = cv2.Canny(gray, 50, 150)
        features['edge_density'] = float(np.sum(edges > 0) / edges.size)
        
        return features
    
    def _calculate_visual_sentiment(self, face_analysis: Dict, 
                                  scene_analysis: Dict, 
                                  visual_features: Dict) -> float:
        """Calculate overall visual sentiment score."""
        
        sentiment_components = []
        weights = []
        
        # Face sentiment (if faces detected)
        if face_analysis['face_count'] > 0:
            sentiment_components.append(face_analysis['average_sentiment'])
            weights.append(0.4)
        
        # Scene sentiment
        sentiment_components.append(scene_analysis['overall_sentiment'])
        weights.append(0.4)
        
        # Visual features sentiment
        visual_sentiment = 0.0
        
        # Brighter images tend to be more positive
        if visual_features['brightness'] > 120:
            visual_sentiment += 0.1
        elif visual_features['brightness'] < 80:
            visual_sentiment -= 0.1
        
        # Good contrast indicates clarity/professionalism
        if visual_features['contrast'] > 50:
            visual_sentiment += 0.05
        
        sentiment_components.append(visual_sentiment)
        weights.append(0.2)
        
        # Weighted average
        if weights:
            total_weight = sum(weights)
            weighted_sentiment = sum(s * w for s, w in zip(sentiment_components, weights))
            return weighted_sentiment / total_weight
        
        return 0.0
    
    def _calculate_visual_confidence(self, face_analysis: Dict, 
                                   scene_analysis: Dict, 
                                   visual_features: Dict) -> float:
        """Calculate confidence in visual sentiment analysis."""
        
        confidence = 0.5  # Base confidence
        
        # Face detection improves confidence
        if face_analysis['face_count'] > 0:
            confidence += 0.2
        
        # Good image quality improves confidence
        if visual_features['contrast'] > 30:
            confidence += 0.15
        
        if visual_features['edge_density'] > 0.1:
            confidence += 0.15
        
        return min(confidence, 1.0)

class MultimodalSentimentAnalyzer:
    """Main class for comprehensive multimodal sentiment analysis."""
    
    def __init__(self, openai_api_key: Optional[str] = None):
        self.text_analyzer = AdvancedTextSentimentAnalyzer()
        self.audio_analyzer = AudioSentimentAnalyzer()
        self.visual_analyzer = VisualSentimentAnalyzer()
        
        # OpenAI client for advanced analysis
        if openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=openai_api_key)
        else:
            self.openai_client = None
        
        # Processing executor
        self.executor = ThreadPoolExecutor(max_workers=4)
        
    async def analyze_earnings_call(self, audio_path: str, 
                                  transcript_path: Optional[str] = None) -> MultimodalSentimentResult:
        """Analyze earnings call audio with optional transcript."""
        
        start_time = asyncio.get_event_loop().time()
        
        # Audio analysis
        audio_result = await self.audio_analyzer.analyze_audio(audio_path)
        
        # Text analysis (from transcript or audio transcription)
        if transcript_path:
            async with aiofiles.open(transcript_path, 'r') as f:
                transcript = await f.read()
        else:
            transcript = audio_result.get('transcription', '')
        
        text_result = await self.text_analyzer.analyze_text(transcript, context="earnings")
        
        # Combine results
        modality_weights = {'text': 0.6, 'audio': 0.4}
        
        overall_sentiment = (
            text_result['sentiment_score'] * modality_weights['text'] +
            audio_result['sentiment_score'] * modality_weights['audio']
        )
        
        confidence = np.mean([text_result['confidence'], audio_result['confidence']])
        
        processing_time = asyncio.get_event_loop().time() - start_time
        
        return MultimodalSentimentResult(
            overall_sentiment=overall_sentiment,
            confidence=confidence,
            modality_weights=modality_weights,
            text_sentiment=text_result['sentiment_score'],
            audio_sentiment=audio_result['sentiment_score'],
            emotions=text_result['emotions'],
            key_phrases=text_result['key_phrases'],
            transcription=transcript,
            processing_time=processing_time,
            source_type="earnings_call"
        )
    
    async def analyze_video_presentation(self, video_path: str) -> MultimodalSentimentResult:
        """Analyze video presentation with audio, visual, and text components."""
        
        start_time = asyncio.get_event_loop().time()
        
        # Extract frames and audio from video
        temp_dir = Path(tempfile.mkdtemp())
        
        try:
            # Extract audio
            video = VideoFileClip(video_path)
            audio_path = temp_dir / "audio.wav"
            video.audio.write_audiofile(str(audio_path), verbose=False, logger=None)
            
            # Extract representative frames
            frame_times = np.linspace(0, video.duration, min(10, int(video.duration)))
            frame_results = []
            
            for i, t in enumerate(frame_times):
                frame = video.get_frame(t)
                frame_path = temp_dir / f"frame_{i}.jpg"
                Image.fromarray(frame.astype('uint8')).save(frame_path)
                
                frame_result = await self.visual_analyzer.analyze_image(str(frame_path))
                frame_results.append(frame_result)
            
            # Audio analysis
            audio_result = await self.audio_analyzer.analyze_audio(str(audio_path))
            
            # Text analysis from transcription
            transcript = audio_result.get('transcription', '')
            text_result = await self.text_analyzer.analyze_text(transcript, context="presentation")
            
            # Visual analysis (average of frames)
            visual_sentiment = np.mean([r['sentiment_score'] for r in frame_results])
            visual_confidence = np.mean([r['confidence'] for r in frame_results])
            
            # Combine results with appropriate weights
            modality_weights = {'text': 0.4, 'audio': 0.3, 'visual': 0.3}
            
            overall_sentiment = (
                text_result['sentiment_score'] * modality_weights['text'] +
                audio_result['sentiment_score'] * modality_weights['audio'] +
                visual_sentiment * modality_weights['visual']
            )
            
            confidence = np.mean([
                text_result['confidence'], 
                audio_result['confidence'], 
                visual_confidence
            ])
            
            # Compile visual features
            visual_features = {
                'frame_count': len(frame_results),
                'average_visual_sentiment': visual_sentiment,
                'frame_details': [r['visual_features'] for r in frame_results]
            }
            
            processing_time = asyncio.get_event_loop().time() - start_time
            
            return MultimodalSentimentResult(
                overall_sentiment=overall_sentiment,
                confidence=confidence,
                modality_weights=modality_weights,
                text_sentiment=text_result['sentiment_score'],
                audio_sentiment=audio_result['sentiment_score'],
                visual_sentiment=visual_sentiment,
                emotions=text_result['emotions'],
                key_phrases=text_result['key_phrases'],
                transcription=transcript,
                visual_features=visual_features,
                processing_time=processing_time,
                source_type="video_presentation"
            )
        
        finally:
            # Cleanup temporary files
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    async def analyze_social_media_content(self, content: Dict[str, Any]) -> MultimodalSentimentResult:
        """Analyze social media content (text, images, videos)."""
        
        start_time = asyncio.get_event_loop().time()
        
        results = []
        modalities = []
        
        # Text analysis
        if 'text' in content and content['text']:
            text_result = await self.text_analyzer.analyze_text(content['text'], context="social")
            results.append(text_result['sentiment_score'])
            modalities.append('text')
        
        # Image analysis
        if 'images' in content and content['images']:
            image_sentiments = []
            for image_path in content['images']:
                image_result = await self.visual_analyzer.analyze_image(image_path)
                image_sentiments.append(image_result['sentiment_score'])
            
            if image_sentiments:
                avg_image_sentiment = np.mean(image_sentiments)
                results.append(avg_image_sentiment)
                modalities.append('visual')
        
        # Video analysis (simplified)
        if 'videos' in content and content['videos']:
            # For social media, we'll just analyze first frame and audio
            video_path = content['videos'][0]  # Take first video
            video_result = await self.analyze_video_presentation(video_path)
            results.append(video_result.overall_sentiment)
            modalities.append('video')
        
        # Calculate weighted sentiment
        if results:
            overall_sentiment = np.mean(results)
            confidence = 0.7  # Moderate confidence for social media
        else:
            overall_sentiment = 0.0
            confidence = 0.0
        
        # Create modality weights
        if modalities:
            weight_per_modality = 1.0 / len(modalities)
            modality_weights = {mod: weight_per_modality for mod in set(modalities)}
        else:
            modality_weights = {}
        
        processing_time = asyncio.get_event_loop().time() - start_time
        
        return MultimodalSentimentResult(
            overall_sentiment=overall_sentiment,
            confidence=confidence,
            modality_weights=modality_weights,
            processing_time=processing_time,
            source_type="social_media"
        )
    
    async def batch_analyze(self, content_list: List[Dict[str, Any]]) -> List[MultimodalSentimentResult]:
        """Batch analyze multiple pieces of content."""
        
        tasks = []
        for content in content_list:
            content_type = content.get('type', 'unknown')
            
            if content_type == 'earnings_call':
                task = self.analyze_earnings_call(
                    content['audio_path'], 
                    content.get('transcript_path')
                )
            elif content_type == 'video_presentation':
                task = self.analyze_video_presentation(content['video_path'])
            elif content_type == 'social_media':
                task = self.analyze_social_media_content(content)
            else:
                # Default to text analysis
                if 'text' in content:
                    task = self._text_only_analysis(content['text'])
                else:
                    continue
            
            tasks.append(task)
        
        return await asyncio.gather(*tasks)
    
    async def _text_only_analysis(self, text: str) -> MultimodalSentimentResult:
        """Fallback text-only analysis."""
        
        text_result = await self.text_analyzer.analyze_text(text)
        
        return MultimodalSentimentResult(
            overall_sentiment=text_result['sentiment_score'],
            confidence=text_result['confidence'],
            modality_weights={'text': 1.0},
            text_sentiment=text_result['sentiment_score'],
            emotions=text_result['emotions'],
            key_phrases=text_result['key_phrases'],
            source_type="text_only"
        )

# Integration with existing news summarizer
async def integrate_multimodal_analysis(articles: List, config: Dict) -> Dict:
    """Integration function for multimodal analysis."""
    
    analyzer = MultimodalSentimentAnalyzer(
        openai_api_key=config.get('openai_api_key')
    )
    
    multimodal_results = []
    
    for article in articles:
        # Check if article has multimedia content
        if hasattr(article, 'multimedia_urls') and article.multimedia_urls:
            content = {
                'type': 'social_media',
                'text': f"{article.title} {article.content}",
                'images': [url for url in article.multimedia_urls if url.endswith(('.jpg', '.png', '.jpeg'))],
                'videos': [url for url in article.multimedia_urls if url.endswith(('.mp4', '.avi', '.mov'))]
            }
            
            result = await analyzer.analyze_social_media_content(content)
            multimodal_results.append(result)
        else:
            # Text-only analysis
            result = await analyzer._text_only_analysis(f"{article.title} {article.content}")
            multimodal_results.append(result)
    
    # Aggregate results
    overall_sentiment = np.mean([r.overall_sentiment for r in multimodal_results])
    avg_confidence = np.mean([r.confidence for r in multimodal_results])
    
    # Extract key insights
    all_emotions = {}
    all_key_phrases = []
    
    for result in multimodal_results:
        if result.emotions:
            for emotion, score in result.emotions.items():
                if emotion not in all_emotions:
                    all_emotions[emotion] = []
                all_emotions[emotion].append(score)
        
        if result.key_phrases:
            all_key_phrases.extend(result.key_phrases)
    
    # Average emotions
    avg_emotions = {emotion: np.mean(scores) for emotion, scores in all_emotions.items()}
    
    # Most common key phrases
    from collections import Counter
    phrase_counts = Counter(all_key_phrases)
    top_phrases = [phrase for phrase, count in phrase_counts.most_common(10)]
    
    return {
        'overall_sentiment': overall_sentiment,
        'confidence': avg_confidence,
        'emotions': avg_emotions,
        'key_phrases': top_phrases,
        'modality_breakdown': {
            'text_only': len([r for r in multimodal_results if r.source_type == 'text_only']),
            'social_media': len([r for r in multimodal_results if r.source_type == 'social_media']),
            'video': len([r for r in multimodal_results if r.source_type == 'video_presentation']),
            'audio': len([r for r in multimodal_results if r.source_type == 'earnings_call'])
        },
        'processing_stats': {
            'total_items': len(multimodal_results),
            'avg_processing_time': np.mean([r.processing_time for r in multimodal_results]),
            'total_processing_time': sum([r.processing_time for r in multimodal_results])
        }
    }

if __name__ == "__main__":
    # Example usage
    async def test_multimodal_analysis():
        analyzer = MultimodalSentimentAnalyzer()
        
        # Test social media content
        social_content = {
            'text': "Apple's earnings call was impressive! Strong iPhone sales and positive guidance.",
            'images': [],  # Would contain image paths
            'videos': []   # Would contain video paths
        }
        
        result = await analyzer.analyze_social_media_content(social_content)
        print(f"Sentiment: {result.overall_sentiment:.3f}")
        print(f"Confidence: {result.confidence:.3f}")
        print(f"Emotions: {result.emotions}")
        print(f"Key phrases: {result.key_phrases}")
    
    # Run test
    asyncio.run(test_multimodal_analysis()) 