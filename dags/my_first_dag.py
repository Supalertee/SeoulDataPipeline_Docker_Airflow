from airflow import DAG
from airflow.utils import timezone  # Corrected spelling of 'utils'
from airflow.operators.empty import EmptyOperator
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

import logging

def _say_hello():
    logging.info("Hello")

with DAG(
    "my_first_dag",
    start_date=timezone.datetime(2024, 8, 24),  # Corrected to start_date and fixed method name
    schedule=None,  # Corrected to schedule_interval
    tags=["ART"],
):

    start = EmptyOperator(
        task_id="start",
    )

    echo_hello = BashOperator(
        task_id="echo_hello",
        bash_command="echo 'hello'",
    )

    say_hello = PythonOperator(
        task_id="say_hello",
        python_callable=_say_hello,
    )

    end = EmptyOperator(
        task_id="end",
    )

    start >> echo_hello >> say_hello >> end
