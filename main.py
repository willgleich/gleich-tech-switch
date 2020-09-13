import googleapiclient.discovery
import logging

import os
from google.cloud import secretmanager

logging.basicConfig(level=logging.INFO)
logging.getLogger('googleapicliet.discovery_cache').setLevel(logging.ERROR)

def create_cloud_run_service(cloud_run, svc_name):
    body = {'apiVersion': 'serving.knative.dev/v1',
            'kind': 'Service',
            'metadata': {'name': svc_name,
                         'namespace': '248394897420',
                         'generation': 1},
            'spec': {'template': {'metadata': {'name': 'gleich-tech-00001-qel',
                                               'annotations': {'run.googleapis.com/client-name': 'cloud-console',
                                                               'autoscaling.knative.dev/maxScale': '1000'}},
                                  'spec': {'containerConcurrency': 80,
                                           'timeoutSeconds': 300,
                                           'containers': [{'image': 'gcr.io/main-285019/resume',
                                                           'resources': {'limits': {'cpu': '1000m', 'memory': '256Mi'}},
                                                           'ports': [{'containerPort': 8080}]}]}},
                     'traffic': [{'percent': 100, 'latestRevision': True}]}}
    return cloud_run.projects().locations().services().create(parent="projects/248394897420/locations/us-west1", body=body).execute()

def delete_cloud_run_service(cloud_run, svc_name):
    return cloud_run.projects().locations().services().delete(name="projects/248394897420/locations/us-west1/services/" + svc_name).execute()

def service_exists(cloud_run, svc_name):
    r = cloud_run.projects().locations().services().list(parent="projects/248394897420/locations/us-west1").execute()
    if "items" in r.keys():
        for run_svc in r["items"]:
            if run_svc["metadata"]["name"] == svc_name:
                return True
    return False

def get_secret(secret_name):
    client = secretmanager.SecretManagerServiceClient()
    secret_name = secret_name
    project_id = os.environ["GCP_PROJECT"]
    resource_name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(resource_name)
    return response.payload.data.decode('UTF-8')

def handler(request):
    logging.info("started the function")
    cloud_run = googleapiclient.discovery.build('run', 'v1')
    logging.info("initalized the cloud_run")
    secret_name = get_secret("cloudflare-api-key")
    if not service_exists(cloud_run, "gleich-tech"):
        svc = create_cloud_run_service(cloud_run, "gleich-tech")
        logging.info("created gleich-tech svc")
        # print(svc)
    else:
        logging.info("svc gleich-tech already exists")
    return f"function moved through successfully"

if __name__ == '__main__':
    handler({})