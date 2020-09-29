import os

from main import CloudRunService

if __name__ == '__main__':
    project_id = os.environ["GCP_PROJECT"]
    gleich_tech = CloudRunService("gleich-tech", project_id, "us-west1")

    gleich_tech.delete()