"""
Saved articles service for the Financial News API.
Allows users to save and manage their favorite articles.
"""

import logging
from typing import Dict, List, Optional
import json
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# In a real app, this would be stored in a database
# For this demo, we'll use a simple file-based storage
SAVED_ARTICLES_DIR = Path(__file__).parent.parent.parent.parent / "data" / "saved_articles"
SAVED_ARTICLES_DIR.mkdir(parents=True, exist_ok=True)


def get_user_saved_articles_path(user_id: str) -> Path:
    """Get the path to a user's saved articles file."""
    return SAVED_ARTICLES_DIR / f"{user_id}_saved_articles.json"


def save_article(user_id: str, article_id: str, article_data: Dict) -> Dict:
    """
    Save an article for a user.
    
    Args:
        user_id: The ID of the user
        article_id: The ID of the article to save
        article_data: Article data to save
        
    Returns:
        Dict with status information
    """
    try:
        # Get the user's saved articles file path
        file_path = get_user_saved_articles_path(user_id)
        
        # Load existing saved articles or create an empty dict
        if file_path.exists():
            with open(file_path, 'r') as f:
                saved_articles = json.load(f)
        else:
            saved_articles = {}
        
        # Add the article to the saved articles
        saved_articles[article_id] = {
            **article_data,
            "saved_at": datetime.now().isoformat()
        }
        
        # Save the updated saved articles
        with open(file_path, 'w') as f:
            json.dump(saved_articles, f, indent=2)
        
        return {
            "status": "success",
            "message": "Article saved successfully",
            "article_id": article_id
        }
    except Exception as e:
        logger.error(f"Error saving article: {e}")
        return {
            "status": "error",
            "message": f"Failed to save article: {str(e)}"
        }


def unsave_article(user_id: str, article_id: str) -> Dict:
    """
    Remove an article from a user's saved articles.
    
    Args:
        user_id: The ID of the user
        article_id: The ID of the article to remove
        
    Returns:
        Dict with status information
    """
    try:
        # Get the user's saved articles file path
        file_path = get_user_saved_articles_path(user_id)
        
        # If the file doesn't exist, there's nothing to unsave
        if not file_path.exists():
            return {
                "status": "error",
                "message": "No saved articles found for this user"
            }
        
        # Load existing saved articles
        with open(file_path, 'r') as f:
            saved_articles = json.load(f)
        
        # Check if the article is in the saved articles
        if article_id not in saved_articles:
            return {
                "status": "error",
                "message": "Article not found in saved articles"
            }
        
        # Remove the article from the saved articles
        del saved_articles[article_id]
        
        # Save the updated saved articles
        with open(file_path, 'w') as f:
            json.dump(saved_articles, f, indent=2)
        
        return {
            "status": "success",
            "message": "Article removed from saved articles"
        }
    except Exception as e:
        logger.error(f"Error unsaving article: {e}")
        return {
            "status": "error",
            "message": f"Failed to remove article: {str(e)}"
        }


def get_saved_articles(user_id: str) -> List[Dict]:
    """
    Get all saved articles for a user.
    
    Args:
        user_id: The ID of the user
        
    Returns:
        List of saved articles
    """
    try:
        # Get the user's saved articles file path
        file_path = get_user_saved_articles_path(user_id)
        
        # If the file doesn't exist, return an empty list
        if not file_path.exists():
            return []
        
        # Load saved articles
        with open(file_path, 'r') as f:
            saved_articles = json.load(f)
        
        # Convert dict to list and add the article_id to each item
        return [
            {**article_data, "id": article_id}
            for article_id, article_data in saved_articles.items()
        ]
    except Exception as e:
        logger.error(f"Error getting saved articles: {e}")
        return []


def is_article_saved(user_id: str, article_id: str) -> bool:
    """
    Check if an article is saved by a user.
    
    Args:
        user_id: The ID of the user
        article_id: The ID of the article to check
        
    Returns:
        True if the article is saved, False otherwise
    """
    try:
        # Get the user's saved articles file path
        file_path = get_user_saved_articles_path(user_id)
        
        # If the file doesn't exist, the article is not saved
        if not file_path.exists():
            return False
        
        # Load saved articles
        with open(file_path, 'r') as f:
            saved_articles = json.load(f)
        
        # Check if the article is in the saved articles
        return article_id in saved_articles
    except Exception as e:
        logger.error(f"Error checking if article is saved: {e}")
        return False
