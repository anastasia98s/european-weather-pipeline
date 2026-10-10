from datetime import datetime

from airflow.sdk import dag, task
from weather_pipeline_script import main


@dag(
    dag_id="european_weather_pipeline",
    schedule="0 6 * * *",
    start_date=datetime(2026, 10, 1),
    catchup=False,
    tags=["weather", "europe"],
)
def european_weather_pipeline():

    @task
    def run_weather_pipeline():
        main()

    run_weather_pipeline()


european_weather_pipeline()
