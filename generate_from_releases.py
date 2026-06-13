#!/usr/bin/env python3
# generate_from_releases.py
# 这个脚本在CI中运行，通过GitHub CLI获取Release信息，生成latest.json

import json
import subprocess
import os
import urllib.request
from datetime import datetime
from pathlib import Path

def get_releases_from_gh_cli():
    """使用GitHub CLI获取所有Releases"""
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    base_cmd = ['gh', 'release']
    if repo:
        base_cmd.extend(['-R', repo])

    try:
        # 获取所有releases的JSON输出
        result = subprocess.run(
            base_cmd + ['list', '--limit', '100', '--json', 'tagName,createdAt,isPrerelease,url,assets'],
            capture_output=True,
            text=True,
            check=True
        )
        releases_data = json.loads(result.stdout)
        print(f"📋 Found {len(releases_data)} releases from gh CLI")
        
        # 获取每个release的详细信息（包括body）
        releases = []
        for release in releases_data:
            try:
                detail = subprocess.run(
                    base_cmd + ['view', release['tagName'], '--json', 'body'],
                    capture_output=True,
                    text=True,
                    check=True
                )
                release_detail = json.loads(detail.stdout)
                
                releases.append({
                    'tag_name': release['tagName'],
                    'published_at': release['createdAt'],
                    'prerelease': release['isPrerelease'],
                    'body': release_detail.get('body', ''),
                    'assets': release['assets'],
                    'html_url': release['url']
                })
            except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
                print(f"⚠️  Failed to fetch details for {release['tagName']}: {e}")
                # 即使获取详情失败，也添加基本信息
                releases.append({
                    'tag_name': release['tagName'],
                    'published_at': release['createdAt'],
                    'prerelease': release['isPrerelease'],
                    'body': '',
                    'assets': release['assets'],
                    'html_url': release['url']
                })
        
        return releases
    except subprocess.CalledProcessError as e:
        print(f"❌ Error calling gh CLI: {e}")
        print(f"   stderr: {e.stderr}")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing gh CLI output: {e}")
        return []

def get_releases_from_api():
    """使用GitHub REST API作为fallback获取Releases"""
    token = os.environ.get('GITHUB_TOKEN', '') or os.environ.get('GH_TOKEN', '')
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    if not repo:
        print("❌ GITHUB_REPOSITORY not set")
        return []
    
    url = f"https://api.github.com/repos/{repo}/releases?per_page=100"
    headers = {
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'GitHub-Action'
    }
    if token:
        headers['Authorization'] = f'Bearer {token}'
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        
        releases = []
        for rel in data:
            releases.append({
                'tag_name': rel['tag_name'],
                'published_at': rel['published_at'] or rel['created_at'],
                'prerelease': rel['prerelease'],
                'body': rel.get('body', ''),
                'assets': [{
                    'name': a['name'],
                    'size': a['size'],
                    'url': a['url'],
                    'browser_download_url': a['browser_download_url']
                } for a in rel.get('assets', [])],
                'html_url': rel['html_url']
            })
        
        print(f"📋 Found {len(releases)} releases from REST API")
        return releases
    except Exception as e:
        print(f"❌ Error calling REST API: {e}")
        return []

def load_local_changelog(version):
    """加载本地changelog文件"""
    changelog_path = Path(f"changelogs/v{version}.json")
    if changelog_path.exists():
        with open(changelog_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def generate_latest_json():
    """生成latest.json（仅最新版本）"""
    releases = get_releases_from_gh_cli()
    if not releases:
        print("⚠️  gh CLI returned no releases, trying REST API fallback...")
        releases = get_releases_from_api()
    
    versions = []
    for release in releases:
        if release['prerelease']:
            continue
            
        version = release['tag_name'].replace('v', '')
        
        # 尝试加载本地changelog
        changelog_data = load_local_changelog(version)
        
        if not changelog_data:
            # 从release body解析changelog
            body = release.get('body', '')
            changelog_data = {
                'summary': '常规更新',
                'changes': parse_changes_from_body(body),
                'type': 'patch',
                'breaking_changes': False,
                'notes': ''
            }
        
        # 获取固件附件
        firmware_assets = []
        for asset in release.get('assets', []):
            if asset['name'].endswith(('.bin', '.hex', '.fw', '.img')) or '.' not in asset['name'].rsplit('/', 1)[-1]:
                firmware_assets.append({
                    'name': asset['name'],
                    'size': asset['size'],
                    'size_mb': round(asset['size'] / (1024 * 1024), 2),
                    'download_url': asset['url'],
                    'browser_download_url': asset.get('browser_download_url', asset['url'])
                })
        
        version_info = {
            'version': version,
            'tag_name': release['tag_name'],
            'release_date': release['published_at'],
            'changelog': changelog_data,
            'release_url': release['html_url'],
            'assets': firmware_assets
        }
        
        if firmware_assets:
            version_info['download_url'] = firmware_assets[0]['browser_download_url']
            version_info['size_mb'] = firmware_assets[0]['size_mb']
        
        versions.append(version_info)
    
    # 按版本排序，取最新
    versions.sort(key=lambda x: [int(i) for i in x['version'].split('.')], reverse=True)
    
    # 生成latest.json
    if versions:
        latest_data = {
            'last_update': datetime.now().isoformat(),
            'latest_version': versions[0]['version'],
            'firmware_info': {
                'version': versions[0]['version'],
                'download_url': versions[0].get('download_url'),
                'size_mb': versions[0].get('size_mb'),
                'release_date': versions[0]['release_date'],
                'changelog': versions[0]['changelog']
            }
        }
    else:
        latest_data = {
            'last_update': datetime.now().isoformat(),
            'latest_version': None,
            'firmware_info': None
        }
    
    with open('latest.json', 'w', encoding='utf-8') as f:
        json.dump(latest_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Generated latest.json (latest version: {versions[0]['version'] if versions else 'N/A'})")

def parse_changes_from_body(body):
    """从Release body解析变更列表"""
    changes = []
    if not body:
        return changes
    
    for line in body.split('\n'):
        line = line.strip()
        if line.startswith('- '):
            changes.append(line[2:])
        elif line.startswith('* '):
            changes.append(line[2:])
    
    return changes if changes else ['请查看Release页面获取详细更新内容']

if __name__ == '__main__':
    generate_latest_json()