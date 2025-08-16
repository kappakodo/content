# compressor.py
import os
import yaml
import json
import base64
import hashlib
from datetime import datetime, date
from io import BytesIO
from PIL import Image
import frontmatter
import re

# Configuration
CONTENT_DIR = 'content'
COMPRESSED_DIR = 'compressed'
IMAGE_MAX_WIDTH = 1280
IMAGE_QUALITY = 80

def serialize_date(obj):
    """Convert datetime.date or datetime.datetime to ISO 8601 string."""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    return obj

def compress_and_encode_image(image_path):
    """Compress image and return base64 data URI."""
    try:
        with Image.open(image_path) as img:
            if img.width > IMAGE_MAX_WIDTH:
                height = int((IMAGE_MAX_WIDTH / img.width) * img.height)
                img = img.resize((IMAGE_MAX_WIDTH, height), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            img_format = img.format or 'JPEG'
            img.save(buffer, format=img_format, quality=IMAGE_QUALITY, optimize=True)
            mime_type = f"image/{img_format.lower()}"
            encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return f"data:{mime_type};base64,{encoded}"
    except Exception as e:
        print(f"   [!] Error compressing {image_path}: {e}")
        return None

def replace_image_paths(content, assets):
    """Replace local image paths in Markdown with base64 data URIs."""
    def replace_match(match):
        img_path = match.group(2)
        img_file = os.path.basename(img_path)
        return f"![{match.group(1)}]({assets.get(img_file, img_path)})"
    
    pattern = r'!\[(.*?)\]\((.*?)\)'
    return re.sub(pattern, replace_match, content)

def process_article(article_dir, category):
    """Process an article folder, return metadata for manifest."""
    md_path = os.path.join(article_dir, 'article.md')
    if not os.path.exists(md_path):
        print(f"Skipping {article_dir}: No article.md")
        return None
    
    with open(md_path, 'r', encoding='utf-8') as f:
        raw_content = f.read()
    
    try:
        post = frontmatter.loads(raw_content)
        metadata = post.metadata
        content = post.content
    except Exception as e:
        print(f"   [!] Error parsing {md_path}: {e}")
        return None
    
    if not metadata.get('title') or not metadata.get('date'):
        print(f"Skipping {article_dir}: Missing title or date")
        return None
    
    # Convert date to string for JSON serialization
    metadata = {k: serialize_date(v) for k, v in metadata.items()}
    
    # Generate unique ID: MD5 of folder name + raw content
    folder_name = os.path.basename(article_dir)
    unique_id = hashlib.md5((folder_name + raw_content).encode('utf-8')).hexdigest()[:12]
    
    # Collect and compress images from images/ subdir
    assets = {}
    images_dir = os.path.join(article_dir, 'images')
    if os.path.exists(images_dir):
        for img_file in os.listdir(images_dir):
            if img_file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                img_path = os.path.join(images_dir, img_file)
                data_uri = compress_and_encode_image(img_path)
                if data_uri:
                    assets[img_file] = data_uri
    
    # Replace image paths in Markdown
    content_with_images = replace_image_paths(content, assets)
    
    # Save as JSON
    article_data = {
        'id': unique_id,
        'metadata': metadata,
        'content_md': content_with_images,
    }
    output_dir = os.path.join(COMPRESSED_DIR, category)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f'{unique_id}.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(article_data, f, indent=2, default=serialize_date)
    
    print(f"Processed {article_dir} -> {output_path}")
    return {
        'id': unique_id,
        'category': category,
        'title': metadata['title'],
        'date': metadata['date'],
        'tags': metadata.get('tags', []),
        'author': metadata.get('author', 'Unknown'),
    }

def generate_manifests(articles):
    """Generate full, latest, and category manifests."""
    articles.sort(key=lambda x: datetime.fromisoformat(x['date']), reverse=True)
    
    # Full manifest
    with open(os.path.join(COMPRESSED_DIR, 'full_manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(articles, f, indent=2, default=serialize_date)
    
    # Latest 10
    with open(os.path.join(COMPRESSED_DIR, 'latest_manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(articles[:10], f, indent=2, default=serialize_date)
    
    # Category manifests
    for category in ['news', 'reviews']:
        category_articles = [a for a in articles if a['category'] == category]
        with open(os.path.join(COMPRESSED_DIR, f'{category}_manifest.json'), 'w', encoding='utf-8') as f:
            json.dump(category_articles, f, indent=2, default=serialize_date)
    
    print("Generated manifests: full_manifest.json, latest_manifest.json, news_manifest.json, reviews_manifest.json")

def main():
    articles = []
    for category in ['news', 'reviews']:
        category_dir = os.path.join(CONTENT_DIR, category)
        if not os.path.exists(category_dir):
            continue
        for subdir in os.listdir(category_dir):
            article_dir = os.path.join(category_dir, subdir)
            if os.path.isdir(article_dir):
                meta = process_article(article_dir, category)
                if meta:
                    articles.append(meta)
    if articles:
        generate_manifests(articles)
    else:
        print("No articles processed")

if __name__ == '__main__':
    main()