import googleapiclient
import logging

class CloudRunService(object):
    '''
    A Class to Handle abstraction of CloudRun service operations
    '''


    def __init__(self, service_name, project, location):
        '''
        :param service_name: Name of either a new or aleady existist service
        :param project: Project name ex: main-285019
        :param location: GCP Region
        '''
        self.service_name = service_name
        self.project = project
        self.location = location
        self.cloud_run = googleapiclient.discovery.build('run', 'v1')


    def _exists(flag):
        '''
        Decorator function to provide proper error reporting depending on whether the service exists or needs to be created
        :return:
        '''
        def decorator(function):
            def inner(self, *args, **kwargs):
                if self.exists() == flag:
                    function(self, *args, **kwargs)
                elif flag:
                    raise ValueError(f"ERROR :: {self.service_name} doesn't exist yet and is required for this operation"
                                     f"It can be created using the CloudRunService.create() method")
                else:
                    raise ValueError(
                        f"ERROR :: {self.service_name} exists already, can't preform operation")
            return inner
        return decorator

    @_exists(False)
    def create(self, image):
        '''
        Creates a new service utilizing the service name, and a required docker image path
        Docker image must be within gcr
        :param image: string
        :return:
        '''
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

    @_exists(True)
    def delete(self):
        '''

        :return: response from cloud_run api
        '''
        return self.cloud_run.projects().locations().services().delete(
            name=f"projects/{self.project}/locations/{self.location}/services/{self.service_name}").execute()

    def exists(self):
        r = self.cloud_run.projects().locations().services().list(
            parent=f"projects/{self.project}/locations/{self.location}").execute()
        if "items" in r.keys():
            for run_svc in r["items"]:
                if run_svc["metadata"]["name"] == self.service_name:
                    return True
        return False

    @_exists(True)
    def allow_unauthenticated(self):
        '''
        Modified the CloudRun Service permissions to allow for unauthenticated access "allUsers" to the cloudrun.invoker
        :return: None
        '''
        policy = {'policy': {'bindings': [{'role': 'roles/run.invoker', 'members': ['allUsers']}]}}
        self.cloud_run.projects().locations().services().setIamPolicy(
            resource=f"projects/{self.project}/locations/{self.location}/services/{self.service_name}",
            body=policy).execute()

    @_exists(True)
    def disallow_unauthenticated(self):
        '''
        Modified the CloudRun Service permissions to allow for unauthenticated access "allUsers" to the cloudrun.invoker
        :return:
        '''
        policy = self.cloud_run.projects().locations().services().getIamPolicy(
            resource=f"projects/{self.project}/locations/{self.location}/services/{self.service_name}").execute()
        #List comp to filter out any rules targeting ['allUsers']
        policy['bindings'] = [x for x in policy['bindings'] if not x['members'] == ['allUsers']]
        policy = {"policy": policy}
        self.cloud_run.projects().locations().services().setIamPolicy(
            resource=f"projects/{self.project}/locations/{self.location}/services/{self.service_name}",
            body=policy).execute()

    @_exists(True)
    def attach_domain(self, domain_name):
        body = {"metadata": {
            "name": domain_name},
            "spec": {
                "routeName": self.service_name,
            },
            "apiVersion": "domains.cloudrun.com/v1",
            "kind": "DomainMapping"
        }
        self.cloud_run.projects().locations().domainmappings().create(
            parent=f"projects/{self.project}/locations/{self.location}", body=body).execute()

monitoring = googleapiclient.discovery.build('monitoring', 'v3')

def get_alert_policy_ids(displayName):
    '''Returns a list of google api names for any alert_policy with a matching displayname'''
    aps = monitoring.projects().alertPolicies().list(name="projects/main-285019").execute()
    if aps == {}:
        return []
    parsed_policies = [check for check in aps['alertPolicies'] if check['displayName'] == displayName]
    return [x['name'] for x in parsed_policies]

def get_uptime_check_ids(displayName):
    '''Returns a list of google api names for any uptime_check with a matching displayname'''
    uptimeChecks = monitoring.projects().uptimeCheckConfigs().list(parent="projects/main-285019").execute()
    if uptimeChecks == {}:
        return []
    parsed_checks = [check for check in uptimeChecks['uptimeCheckConfigs'] if check['displayName'] == displayName]
    return [x['name'] for x in parsed_checks]

def remove_check_and_alert(uptimeName, alertName=None):
    '''Removes check_uptime and alert_policy configuration with the matching displaynames'''
    if alertName is None:
        alertName = uptimeName
    for ap_id in get_alert_policy_ids(alertName):
        monitoring.projects().alertPolicies().delete(name=ap_id).execute()
        logging.info(f"deleted {ap_id}")
    for up_id in get_uptime_check_ids(uptimeName):
        monitoring.projects().uptimeCheckConfigs().delete(name=up_id).execute()
        logging.info(f"deleted {up_id}")
    return "deleted the logged check_uptimes and alerts"

def create_gleich_tech_check_uptime(displayName):
    body = {'displayName': displayName,
       'monitoredResource': {'type': 'uptime_url',
        'labels': {'project_id': 'main-285019', 'host': 'will.gleich.tech'}},
       'httpCheck': {'useSsl': True,
        'path': '/',
        'port': 443,
        'validateSsl': True,
        'requestMethod': 'GET'},
       'period': '60s',
       'timeout': '5s'}
    resp = monitoring.projects().uptimeCheckConfigs().create(parent="projects/main-285019", body = body).execute()
    return resp['displayName']

def create_gleich_tech_alert_policy(displayName, check_uptime_displayName):
    uptime_id = check_uptime_displayName.split('/')[-1]
    body = {'displayName': 'gleich-tech-alert',
       'combiner': 'OR',
       'conditions': [{'conditionThreshold': {'filter': 'metric.type="monitoring.googleapis.com/uptime_check/check_passed" resource.type="uptime_url" metric.label."check_id"="'+ uptime_id + '"',
          'comparison': 'COMPARISON_GT',
          'thresholdValue': 1,
          'duration': '60s',
          'trigger': {'count': 1},
          'aggregations': [{'alignmentPeriod': '1200s',
            'perSeriesAligner': 'ALIGN_NEXT_OLDER',
            'crossSeriesReducer': 'REDUCE_COUNT_FALSE',
            'groupByFields': ['resource.*']}]},
         'displayName': 'Uptime Health Check on will.gleich.tech'}],
       'notificationChannels': ['projects/main-285019/notificationChannels/10740624598998404152',
        'projects/main-285019/notificationChannels/14761312651395586477'],
       'enabled': True}
    ap.create(name="projects/main-285019", body=body).execute()

def create_check_and_alert(uptimeName, alertName=None):
    '''Removes check_uptime and alert_policy configuration with the matching displaynames'''
    if alertName is None:
        alertName = uptimeName
    check_uptime_displayName = create_gleich_tech_check_uptime(uptimeName)
    create_gleich_tech_alert_policy(alertName, check_uptime_displayName)
    return "completed"