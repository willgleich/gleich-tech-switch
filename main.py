import googleapiclient.discovery
import logging

import os
from google.cloud import secretmanager

logging.basicConfig(level=logging.INFO)
logging.getLogger('googleapicliet.discovery_cache').setLevel(logging.ERROR)


class cloud_run_service(object):
    def __init__(self, service_name, project, location):
        self.service_name = service_name
        self.project = project
        self.location = location
        self.cloud_run = googleapiclient.discovery.build('run', 'v1')

    def create(self, image):
        body = {'apiVersion': 'serving.knative.dev/v1',
                'kind': 'Service',
                'metadata': {'name': self.service_name,
                             'namespace': '248394897420',
                             'generation': 1},
                'spec': {'template': {'metadata': {'name': f"{self.service_name}-00001-qel",
                                                   'annotations': {'run.googleapis.com/client-name': 'cloud-console',
                                                                   'autoscaling.knative.dev/maxScale': '1000'}},
                                      'spec': {'containerConcurrency': 80,
                                               'timeoutSeconds': 300,
                                               'containers': [{'image': image,
                                                               'resources': {
                                                                   'limits': {'cpu': '1000m', 'memory': '256Mi'}},
                                                               'ports': [{'containerPort': 8080}]}]}},
                         'traffic': [{'percent': 100, 'latestRevision': True}]}}
        return self.cloud_run.projects().locations().services().create(
            parent=f"projects/{self.project}/locations/{self.location}", body=body).execute()

    def delete(self):
        return self.cloud_run.projects().locations().services().delete(
            name=f"projects/{self.project}/locations/{self.location}/services/" + self.service_name).execute()

    def exists(self):
        r = self.cloud_run.projects().locations().services().list(
            parent=f"projects/{self.project}/locations/us-west1").execute()
        if "items" in r.keys():
            for run_svc in r["items"]:
                if run_svc["metadata"]["name"] == self.service_name:
                    return True
        return False

    def allow_unauthenticated(self):
        policy = {'policy': {'bindings': [{'role': 'roles/run.invoker', 'members': ['allUsers']}]}}
        self.cloud_run.projects().locations().services().setIamPolicy(
            resource=f"projects/{self.project}/locations/{self.location}/services/{self.service_name}",
            body=policy).execute()

    def attach_domain(self, domain_name):
        body = {"metadata": {
            "name": domain_name},
            "spec": {
                "routeName": self.service_name,
            },
            "apiVersion": "domains.cloudrun.com/v1",
            "kind": "DomainMapping"
        }
        self.cloud_run.projects().locations().domainmappings().create(parent=f"projects/{self.project}/locations/{self.location}",
                                                                 body=body).execute()

def get_secret(secret_name):
    client = secretmanager.SecretManagerServiceClient()
    secret_name = secret_name
    project_id = os.environ["GCP_PROJECT"]
    resource_name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(name=resource_name)
    return response.payload.data.decode('UTF-8')


def gleich_switch(request):
    gleich_tech = cloud_run_service("gleich-tech", "248394897420", "us-west1")
    logging.info("started the function")
    logging.info("initalized the cloud_run")
    secret_name = get_secret("cloudflare-api-key")
    if not gleich_tech.exists():
        svc = gleich_tech.create("gcr.io/main-285019/resume")
        logging.info("created gleich-tech svc")
        gleich_tech.allow_unauthenticated()
        gleich_tech.attach_domain("william.gleich.tech")
    else:
        logging.info("svc gleich-tech already exists")
    return f"function moved through successfully"


if __name__ == '__main__':
    gleich_switch({})
