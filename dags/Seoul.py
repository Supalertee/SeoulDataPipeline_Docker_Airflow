from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils import timezone
import datetime
import requests
import logging
import json

def _get_seoul_api():
    response = requests.get('https://api.waqi.info/feed/@5508/?token=1f58ac16d8aa14631599aae7f7637d353551a70b')
    data = response.json()
    logging.info(data)
    with open(str("/opt/airflow/dags/AirPollutionSeoul/realtime"+str(datetime.datetime.now().date())+".json"),"w") as f :
        json.dump(data,f)
        f.write("\n")

def _sqlspark_data():
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.appName('practise').getOrCreate() 
    # df_pyspark = spark.read.option('header','true').csv('dags/AirPollutionSeoul/Measurement_summary.csv')
    df_pyspark = spark.read.csv(
    path = "dags/AirPollutionSeoul/Measurement_summary.csv",
    header = True,
    )
    df_pyspark = df_pyspark.withColumnRenamed("PM2.5","PM25")



def _pandas_data():
    import pandas as pd 
    Seoul = pd.read_csv("/opt/airflow/dags/AirPollutionSeoul/Measurement_summary.csv")
    Seoulmod = Seoul.copy()
    Seoulmod["Measurement date"]=Seoulmod["Measurement date"].str.slice(0,4)
    Seoulmod["Address"]=Seoulmod["Address"].str.split(',').str[2].str.strip()

    Seoulall =Seoulmod.drop(["Measurement date"],axis=1).groupby('Address').mean().reset_index()
    Seoul2017 = Seoulmod[Seoulmod["Measurement date"]=="2017"].drop("Measurement date",axis=1)\
        .groupby(["Station code","Address","Latitude","Longitude"]).mean().reset_index()
    Seoul2018 = Seoulmod[Seoulmod["Measurement date"]=="2018"].drop("Measurement date",axis=1)\
        .groupby(["Station code","Address","Latitude","Longitude"]).mean().reset_index()
    Seoul2019 = Seoulmod[Seoulmod["Measurement date"]=="2019"].drop("Measurement date",axis=1)\
        .groupby(["Station code","Address","Latitude","Longitude"]).mean().reset_index()

    Seoulall.to_csv("/opt/airflow/dags/AirPollutionSeoul/all.csv", index=False)
    Seoul2017.to_csv("/opt/airflow/dags/AirPollutionSeoul/2017.csv", index=False)
    Seoul2018.to_csv("/opt/airflow/dags/AirPollutionSeoul/2018.csv", index=False)
    Seoul2019.to_csv("/opt/airflow/dags/AirPollutionSeoul/2019.csv", index=False)
    

def _geomerge_plot() :
        import geopandas as gpd
        import pandas as pd
        import matplotlib.pyplot as plt

        Seoulall = pd.read_csv("/opt/airflow/dags/AirPollutionSeoul/all.csv")
        Seoul2017 = pd.read_csv("/opt/airflow/dags/AirPollutionSeoul/2017.csv")
        Seoul2018 = pd.read_csv("/opt/airflow/dags/AirPollutionSeoul/2018.csv")
        Seoul2019 = pd.read_csv("/opt/airflow/dags/AirPollutionSeoul/2019.csv")
        tempSeoulGep=gpd.read_file("/opt/airflow/plugins/seoul_municipalities_geo.json")
        SeoulGeo_pollution2017 = tempSeoulGep.merge(Seoul2017, left_on='SIG_ENG_NM', right_on='Address').drop("Address",axis=1)
        SeoulGeo_pollution2018 = tempSeoulGep.merge(Seoul2018, left_on='SIG_ENG_NM', right_on='Address').drop("Address",axis=1)
        SeoulGeo_pollution2019 = tempSeoulGep.merge(Seoul2019, left_on='SIG_ENG_NM', right_on='Address').drop("Address",axis=1)
        maxdata=Seoulall.iloc[:,1:].max()
        mindata=Seoulall.iloc[:,1:].min()

        f, axes = plt.subplots(figsize=(5, 15), ncols=3, nrows=4,layout="compressed")
        SeoulGeo_pollution2017.plot(ax=axes[0][0], column='PM2.5', cmap='OrRd', legend=True, legend_kwds={"label": "", "orientation": "horizontal"},vmin = mindata["PM2.5"],vmax = maxdata["PM2.5"])
        SeoulGeo_pollution2017.plot(ax=axes[1][0], column='PM10', cmap='OrRd', legend=True, legend_kwds={"label": "", "orientation": "horizontal"},vmin = mindata["PM10"],vmax = maxdata["PM10"])
        SeoulGeo_pollution2017.plot(ax=axes[2][0], column='CO', cmap='OrRd', legend=True, legend_kwds={"label": "", "orientation": "horizontal"},vmin = mindata["CO"],vmax = maxdata["CO"])
        SeoulGeo_pollution2017.plot(ax=axes[3][0], column='SO2', cmap='OrRd', legend=True, legend_kwds={"label": "", "orientation": "horizontal"},vmin = mindata["SO2"],vmax = maxdata["SO2"])
        SeoulGeo_pollution2018.plot(ax=axes[0][1], column='PM2.5', cmap='OrRd', legend=True, legend_kwds={"label": "PM2.5", "orientation": "horizontal"},vmin = mindata["PM2.5"],vmax = maxdata["PM2.5"])
        SeoulGeo_pollution2018.plot(ax=axes[1][1], column='PM10', cmap='OrRd', legend=True, legend_kwds={"label": "PM10", "orientation": "horizontal"},vmin = mindata["PM10"],vmax = maxdata["PM10"])
        SeoulGeo_pollution2018.plot(ax=axes[2][1], column='CO', cmap='OrRd', legend=True, legend_kwds={"label": "CO", "orientation": "horizontal"},vmin = mindata["CO"],vmax = maxdata["CO"])
        SeoulGeo_pollution2018.plot(ax=axes[3][1], column='SO2', cmap='OrRd', legend=True, legend_kwds={"label": "SO2", "orientation": "horizontal"},vmin = mindata["SO2"],vmax = maxdata["SO2"])
        SeoulGeo_pollution2019.plot(ax=axes[0][2], column='PM2.5', cmap='OrRd', legend=True, legend_kwds={"label": "", "orientation": "horizontal"},vmin = mindata["PM2.5"],vmax = maxdata["PM2.5"])
        SeoulGeo_pollution2019.plot(ax=axes[1][2], column='PM10', cmap='OrRd', legend=True, legend_kwds={"label": "", "orientation": "horizontal"},vmin = mindata["PM10"],vmax = maxdata["PM10"])
        SeoulGeo_pollution2019.plot(ax=axes[2][2], column='CO', cmap='OrRd', legend=True, legend_kwds={"label": "", "orientation": "horizontal"},vmin = mindata["CO"],vmax = maxdata["CO"])
        SeoulGeo_pollution2019.plot(ax=axes[3][2], column='SO2', cmap='OrRd', legend=True, legend_kwds={"label": "", "orientation": "horizontal"},vmin = mindata["SO2"],vmax = maxdata["SO2"])

        for i, ax_row in enumerate(axes):
            for j, ax in enumerate(ax_row):
                ax.set_xticks([])
                ax.set_yticks([])
                if i ==0:
                    if j == 0:
                        ax.set_title("2017" , fontsize=12)
                    elif j==1:
                        ax.set_title("2018" , fontsize=12)
                    else:
                        ax.set_title("2019" , fontsize=12)
                else:
                    ax.set_title(" ")
        plt.savefig("/opt/airflow/dags/geo_map.png")

def _correlation_plot():
        import pandas as pd 
        import seaborn as sns
        import matplotlib.pyplot as plt
        import numpy as np
        Seoulmod = pd.read_csv("/opt/airflow/dags/AirPollutionSeoul/Measurement_summary.csv")
        Seoulmod["Measurement date"]=Seoulmod["Measurement date"].str.slice(0,7)
        Seoulmod["Address"]=Seoulmod["Address"].str.split(',').str[2].str.strip()
        Seoulmod = Seoulmod.drop(["Latitude","Longitude","Station code"],axis=1)
        Seoulmod.insert(0,"M",Seoulmod["Measurement date"].str.slice(5,7),True)
        Seoulmod.insert(1,"Y",Seoulmod["Measurement date"].str.slice(0,4),True)
        Seoulmod.drop("Measurement date",axis=1,inplace=True)
        pre_plot = Seoulmod.drop(["Y"],axis=1).groupby(["Address","M"],as_index = False).mean()

        plot_temp= pre_plot.drop(["Address","M"],axis=1)
        fig1 = plt.figure(figsize=(12,5))
        corr= plot_temp.corr()
        matrix = np.triu(corr)
        cmap = sns.diverging_palette(230, 20, as_cmap=True)
        sns.heatmap(corr,annot=True, mask=matrix, cmap=cmap)
        plt.savefig("/opt/airflow/dags/correlation1.png")

        fig,axes = plt.subplots(figsize=(6, 6), ncols=2, nrows=3,layout="compressed")
        sns.regplot(x="PM2.5",y="PM10",data = plot_temp, ax=axes[0,0],line_kws={"color": "red"})
        sns.residplot(x="PM2.5",y="PM10",data = plot_temp, ax=axes[0,1])
        sns.regplot(x="O3",y="CO",data = plot_temp, ax=axes[1,0],line_kws={"color": "red"})
        sns.residplot(x="O3",y="CO",data = plot_temp, ax=axes[1,1])
        sns.regplot(x="O3",y="SO2",data = plot_temp, ax=axes[2,0],line_kws={"color": "red"})
        sns.residplot(x="O3",y="SO2",data = plot_temp, ax=axes[2,1])
        plt.savefig("/opt/airflow/dags/correlation2.png")

with DAG(
    "download_air_pollution_data",
    start_date= timezone.datetime(2024, 8, 24),  # Start the DAG one day ago, to make it immediately available
    schedule_interval=None,  # No schedule, manual or trigger-based execution
    tags=["kaggle"],  # Tags for organizing DAGs in the UI
):

    start = EmptyOperator(
        task_id = "start"
    )

    download_dataset_api = BashOperator(
    task_id="download_dataset_api",
    bash_command=(
       "kaggle datasets download -d bappekim/air-pollution-in-seoul -p /opt/airflow/dags --unzip"
    ),
    )

    get_seoul_api_realtime = PythonOperator(
        task_id = "get_seoul_api",
        python_callable = _get_seoul_api,
    )
    spark_test = PythonOperator(
         task_id = "spark_test",
         python_callable = _sqlspark_data
    )

    dataset2pandas = PythonOperator(
        task_id= "dataset2pandas",
        python_callable = _pandas_data,
    )
    
    geo_map_plot = PythonOperator(
        task_id = "geo_map_plot",
        python_callable = _geomerge_plot,
    )
    correlation_plot = PythonOperator(
         task_id = "correlation_plot",
         python_callable = _correlation_plot,
    )

    stop = EmptyOperator(
        task_id = "stop"
    )

    # Define task dependencies (if any)
    # In this case, there's only one task, so no dependencies are needed

    start >> download_dataset_api >>spark_test>>  dataset2pandas >> geo_map_plot  >> stop
    dataset2pandas >> get_seoul_api_realtime >> stop 
    dataset2pandas >> correlation_plot >> stop
    

