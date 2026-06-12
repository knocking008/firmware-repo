# generate_version_json.py
import os
import json
import re
import hashlib
from datetime import datetime
from pathlib import Path

def extract_version_from_filename(filename):
    """从文件名提取版本号"""
    patterns = [
        r'v?(\d+\.\d+\.\d+)',  # v1.0.0 或 1.0.0
        r'(\d+\.\d+\.\d+\.\d+)',  # 1.0.0.0
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            return match.group(1)
    return None

def get_file_hash(filepath):
    """计算文件SHA256"""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def generate_version_json(firmware_dir="firmware", output_file="versions.json"):
    """生成版本信息JSON"""
    versions = []
    firmware_path = Path(firmware_dir)
    
    for file_path in firmware_path.rglob("*"):
        if file_path.is_file() and file_path.suffix in ['.bin', '.hex', '.fw', '.6']:
            version = extract_version_from_filename(file_path.name)
            if version:
                file_size = file_path.stat().st_size
                file_hash = get_file_hash(file_path)
                
                # 获取Git LFS URL（需要在GitHub上）
                raw_url = f"https://raw.githubusercontent.com/knocking008/firmware-repo/main/{file_path}"
                
                versions.append({
                    "version": version,
                    "filename": file_path.name,
                    "size": file_size,
                    "size_mb": round(file_size / (1024 * 1024), 2),
                    "sha256": file_hash,
                    "download_url": raw_url,
                    "release_date": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                    "changelog": f"https://github.com/knocking008/firmware-repo/releases/tag/v{version}"
                })
    
    # 按版本号排序
    versions.sort(key=lambda x: [int(i) for i in x['version'].split('.')], reverse=True)
    
    # 生成完整版本列表
    version_data = {
        "last_update": datetime.now().isoformat(),
        "total_versions": len(versions),
        "versions": versions,
        "latest": versions[0] if versions else None
    }
    
    # 写入文件
    with open(output_file, 'w') as f:
        json.dump(version_data, f, indent=2)
    
    # 同时生成latest.json
    latest_data = {
        "last_update": datetime.now().isoformat(),
        "latest_version": versions[0]["version"] if versions else None,
        "firmware_info": versions[0] if versions else None
    }
    
    with open("latest.json", 'w') as f:
        json.dump(latest_data, f, indent=2)
    
    print(f"Generated {output_file} with {len(versions)} versions")

if __name__ == "__main__":
    generate_version_json()