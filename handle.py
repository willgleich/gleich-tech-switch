import googleapiclient.discovery

def create_cloud_run_service(cloud_run):
    body = {'apiVersion': 'serving.knative.dev/v1',
            'kind': 'Service',
            'metadata': {'name': 'gleich-tech',
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

def handler(request):
    cloud_run = googleapiclient.discovery.build('run', 'v1')
    svc = create_cloud_run_service(cloud_run)
    print(svc)

if __name__ == '__main__':
    cloud_run = googleapiclient.discovery.build('run', 'v1')
    svc = create_cloud_run_service(cloud_run)
    print(svc)
