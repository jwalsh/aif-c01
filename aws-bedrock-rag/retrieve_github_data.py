import os
import requests

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')

def get_org_repos(org_name):
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    url = f'https://api.github.com/orgs/{org_name}/repos'
    response = requests.get(url, headers=headers)
    response.raise_for_status()  # Raise an exception for bad responses
    return response.json()

def get_repo_contents(repo_owner, repo_name):
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    url = f'https://api.github.com/repos/{repo_owner}/{repo_name}/contents'
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def download_file(download_url, local_path):
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    response = requests.get(download_url, headers=headers)
    response.raise_for_status()
    with open(local_path, 'wb') as f:
        f.write(response.content)

if __name__ == "__main__":
    org_name = "defrecord"  # Replace with your organization name
    repos = get_org_repos(org_name)

    for repo in repos:
        repo_owner = repo['owner']['login']
        repo_name = repo['name']
        contents = get_repo_contents(repo_owner, repo_name)

        for item in contents:
            if item['type'] == 'file':
                download_url = item['download_url']
                local_path = os.path.join('repo_data', repo_name, item['path'])
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                download_file(download_url, local_path)
                print(f"Downloaded {local_path}")
