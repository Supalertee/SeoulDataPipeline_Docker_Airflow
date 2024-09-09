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
        
def _sqlspark_data_refining():
    from pyspark.sql import SparkSession
    from pyspark.sql.types import IntegerType,BooleanType,DateType
    from pyspark.sql.functions import col, split, trim, substring 


    spark = SparkSession.builder.appName('practise').getOrCreate() 
    df_pyspark = spark.read.csv(
    path = "/opt/airflow/dags/AirPollutionSeoul/Measurement_summary.csv",
    header = True,
    )
    df_pyspark = df_pyspark.withColumnRenamed("PM2.5","PM25")
    columns_to_cast = ["PM25", "PM10", "SO2", "CO", "NO2", "O3"]

    for col_name in columns_to_cast:
        df_pyspark = df_pyspark.withColumn(col_name, df_pyspark[col_name].cast('float'))

    df_stat = df_pyspark.summary().cache()
    pm25_cutoff_max = float(df_stat.collect()[1]["PM25"])+(2*float(df_stat.collect()[2]["PM25"]))
    pm10_cutoff_max = float(df_stat.collect()[1]["PM10"])+(2*float(df_stat.collect()[2]["PM10"]))
    so2_cutoff_max  = float(df_stat.collect()[1]["SO2"])+(2*float(df_stat.collect()[2]["SO2"]))
    co_cutoff_max   = float(df_stat.collect()[1]["CO"])+(2*float(df_stat.collect()[2]["CO"]))
    no2_cutoff_max  = float(df_stat.collect()[1]["NO2"])+(2*float(df_stat.collect()[2]["NO2"]))
    o3_cutoff_max   = float(df_stat.collect()[1]["O3"])+(2*float(df_stat.collect()[2]["O3"]))

    pm25_cutoff_min = float(df_stat.collect()[4]["PM25"])/2
    pm10_cutoff_min = float(df_stat.collect()[4]["PM10"])/2
    so2_cutoff_min = float(df_stat.collect()[4]["SO2"])/2
    co_cutoff_min  = float(df_stat.collect()[4]["CO"])/2
    no2_cutoff_min  = float(df_stat.collect()[4]["NO2"])/2
    o3_cutoff_min  = float(df_stat.collect()[4]["O3"])/2
    

    df_pyspark = df_pyspark.filter((df_pyspark["PM25"] >= pm25_cutoff_min )   &   (df_pyspark["PM25"] < pm25_cutoff_max)    &
                   (df_pyspark["PM10"] >= pm10_cutoff_min)      &   (df_pyspark["PM10"] < pm10_cutoff_max ) &
                   (df_pyspark["SO2"]>= so2_cutoff_min)         &   (df_pyspark["SO2"] < so2_cutoff_max )   &
                   (df_pyspark["NO2"]>= no2_cutoff_min)         &   (df_pyspark["NO2"] < no2_cutoff_max )   &
                   (df_pyspark["O3"]>=  o3_cutoff_min)          &   (df_pyspark["O3"] < o3_cutoff_max )     &
                   (df_pyspark["CO"]>=  co_cutoff_min)          &   (df_pyspark["CO"] < co_cutoff_max ) )
    
    Seoul_MY =  df_pyspark.withColumn("Measurement date", substring(col("Measurement date"), 1, 7)).withColumn("Address", trim(split(col("Address"), ",").getItem(2)))
    
    df_pyspark =  df_pyspark.withColumn("Measurement date", substring(col("Measurement date"), 1, 4))
    df_pyspark =  df_pyspark.withColumn("Address", trim(split(col("Address"), ",").getItem(2)))
    Seoul2017 = df_pyspark.filter(df_pyspark["Measurement date"] == 2017)
    Seoul2018 = df_pyspark.filter(df_pyspark["Measurement date"] == 2018)
    Seoul2019 = df_pyspark.filter(df_pyspark["Measurement date"] == 2019)
    Seoul_MY.write.format("csv").option("header", "true").mode("overwrite").save("/opt/airflow/dags/AirPollutionSeoul/Seoul_MY")
    Seoul2017.write.format("csv").option("header", "true").mode("overwrite").save("/opt/airflow/dags/AirPollutionSeoul/2017")
    Seoul2018.write.format("csv").option("header", "true").mode("overwrite").save("/opt/airflow/dags/AirPollutionSeoul/2018")
    Seoul2019.write.format("csv").option("header", "true").mode("overwrite").save("/opt/airflow/dags/AirPollutionSeoul/2019")



def _geomerge_plot() :
    import os
    import geopandas as gpd
    import matplotlib.pyplot as plt
    from pyspark.sql import SparkSession
    import pyspark.pandas as ps
    from matplotlib.colors import Normalize

# Initialize Spark session
    spark = SparkSession.builder.appName('spark').getOrCreate()

# Load data from CSV files into Spark DataFrames
    Seoul_all = spark.read.format("csv").option("header", "true").load("/opt/airflow/dags/AirPollutionSeoul/Seoul_MY")
    Seoul2017 = spark.read.format("csv").option("header", "true").load("/opt/airflow/dags/AirPollutionSeoul/2017")
    Seoul2018 = spark.read.format("csv").option("header", "true").load("/opt/airflow/dags/AirPollutionSeoul/2018")
    Seoul2019 = spark.read.format("csv").option("header", "true").load("/opt/airflow/dags/AirPollutionSeoul/2019")


    pollution_columns = ['SO2', 'NO2', 'O3', 'CO', 'PM10', 'PM25']
    for col in pollution_columns:
        Seoul_all = Seoul_all.withColumn(col, Seoul_all[col].cast('float'))
        Seoul2017 = Seoul2017.withColumn(col, Seoul2017[col].cast('float'))
        Seoul2018 = Seoul2018.withColumn(col, Seoul2018[col].cast('float'))
        Seoul2019 = Seoul2019.withColumn(col, Seoul2019[col].cast('float'))
    # Group by 'Address' and calculate the average for each pollution column

    # # Load GeoJSON data into a GeoDataFrame
    tempSeoulGep = gpd.read_file("/opt/airflow/plugins/seoul_municipalities_geo.json")


    Seoul_all = Seoul_all.toPandas()
    Seoul2017 = Seoul2017.toPandas()
    Seoul2018 = Seoul2018.toPandas()
    Seoul2019 = Seoul2019.toPandas()


    Seoul_all =Seoul_all.drop(["Measurement date","Station code" , "Station code","Address","Latitude","Longitude"],axis=1)
    Seoul2017 = Seoul2017[Seoul2017["Measurement date"]=="2017"].drop("Measurement date",axis=1)\
        .groupby(["Station code","Address","Latitude","Longitude"]).mean().reset_index()
    Seoul2018 = Seoul2018[Seoul2018["Measurement date"]=="2018"].drop("Measurement date",axis=1)\
        .groupby(["Station code","Address","Latitude","Longitude"]).mean().reset_index()
    Seoul2019 = Seoul2019[Seoul2019["Measurement date"]=="2019"].drop("Measurement date",axis=1)\
        .groupby(["Station code","Address","Latitude","Longitude"]).mean().reset_index()
    maxdata=Seoul_all.iloc[:,0:].max()
    mindata=Seoul_all.iloc[:,0:].min()

    SeoulGeo_pollution2017 = tempSeoulGep.merge(Seoul2017, left_on='SIG_ENG_NM', right_on='Address').drop("Address", axis=1)
    SeoulGeo_pollution2018 = tempSeoulGep.merge(Seoul2018, left_on='SIG_ENG_NM', right_on='Address').drop("Address", axis=1)
    SeoulGeo_pollution2019 = tempSeoulGep.merge(Seoul2019, left_on='SIG_ENG_NM', right_on='Address').drop("Address", axis=1)



    Pollution_key = ["PM25", "PM10","SO2","CO"]
    f, axes = plt.subplots(figsize=(5, 15), ncols = 3, nrows = 4,layout="compressed")
    for i,keys in enumerate(Pollution_key): 
        SeoulGeo_pollution2017.plot(ax=axes[i][0], column= keys, cmap='OrRd', legend=True, 
                                    legend_kwds={"label": "", "orientation": "horizontal"})
        SeoulGeo_pollution2018.plot(ax=axes[i][1], column=keys, cmap='OrRd', legend=True, 
                                    legend_kwds={"label": keys, "orientation": "horizontal"})
        SeoulGeo_pollution2019.plot(ax=axes[i][2], column= keys , cmap='OrRd', legend=True, 
                                    legend_kwds={"label": "", "orientation": "horizontal"} ,)

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

# def _geomerge_plot() : (PANDAS)
#         import geopandas as gpd
#         import pandas as pd
#         import matplotlib.pyplot as plt

#         Seoul = pd.read_csv("/opt/airflow/dags/AirPollutionSeoul/Measurement_summary.csv")
#         Seoulmod = Seoul.copy()
#         Seoulmod["Measurement date"]=Seoulmod["Measurement date"].str.slice(0,4)
#         Seoulmod["Address"]=Seoulmod["Address"].str.split(',').str[2].str.strip()

#         Seoulall =Seoulmod.drop(["Measurement date"],axis=1).groupby('Address').mean().reset_index()
#         Seoul2017 = Seoulmod[Seoulmod["Measurement date"]=="2017"].drop("Measurement date",axis=1)\
#             .groupby(["Station code","Address","Latitude","Longitude"]).mean().reset_index()
#         Seoul2018 = Seoulmod[Seoulmod["Measurement date"]=="2018"].drop("Measurement date",axis=1)\
#             .groupby(["Station code","Address","Latitude","Longitude"]).mean().reset_index()
#         Seoul2019 = Seoulmod[Seoulmod["Measurement date"]=="2019"].drop("Measurement date",axis=1)\
#             .groupby(["Station code","Address","Latitude","Longitude"]).mean().reset_index()
        
#         tempSeoulGep=gpd.read_file("/opt/airflow/plugins/seoul_municipalities_geo.json")
#         SeoulGeo_pollution2017 = tempSeoulGep.merge(Seoul2017, left_on='SIG_ENG_NM', right_on='Address').drop("Address",axis=1)
#         SeoulGeo_pollution2018 = tempSeoulGep.merge(Seoul2018, left_on='SIG_ENG_NM', right_on='Address').drop("Address",axis=1)
#         SeoulGeo_pollution2019 = tempSeoulGep.merge(Seoul2019, left_on='SIG_ENG_NM', right_on='Address').drop("Address",axis=1)
#         maxdata=Seoulall.iloc[:,1:].max()
#         mindata=Seoulall.iloc[:,1:].min()

#         f, axes = plt.subplots(figsize=(5, 15), ncols=3, nrows=4,layout="compressed")
#         SeoulGeo_pollution2017.plot(ax=axes[0][0], column='PM2.5', cmap='OrRd', legend=True, legend_kwds={"label": "", "orientation": "horizontal"},vmin = mindata["PM2.5"],vmax = maxdata["PM2.5"])
#         SeoulGeo_pollution2017.plot(ax=axes[1][0], column='PM10', cmap='OrRd', legend=True, legend_kwds={"label": "", "orientation": "horizontal"},vmin = mindata["PM10"],vmax = maxdata["PM10"])
#         SeoulGeo_pollution2017.plot(ax=axes[2][0], column='CO', cmap='OrRd', legend=True, legend_kwds={"label": "", "orientation": "horizontal"},vmin = mindata["CO"],vmax = maxdata["CO"])
#         SeoulGeo_pollution2017.plot(ax=axes[3][0], column='SO2', cmap='OrRd', legend=True, legend_kwds={"label": "", "orientation": "horizontal"},vmin = mindata["SO2"],vmax = maxdata["SO2"])
#         SeoulGeo_pollution2018.plot(ax=axes[0][1], column='PM2.5', cmap='OrRd', legend=True, legend_kwds={"label": "PM2.5", "orientation": "horizontal"},vmin = mindata["PM2.5"],vmax = maxdata["PM2.5"])
#         SeoulGeo_pollution2018.plot(ax=axes[1][1], column='PM10', cmap='OrRd', legend=True, legend_kwds={"label": "PM10", "orientation": "horizontal"},vmin = mindata["PM10"],vmax = maxdata["PM10"])
#         SeoulGeo_pollution2018.plot(ax=axes[2][1], column='CO', cmap='OrRd', legend=True, legend_kwds={"label": "CO", "orientation": "horizontal"},vmin = mindata["CO"],vmax = maxdata["CO"])
#         SeoulGeo_pollution2018.plot(ax=axes[3][1], column='SO2', cmap='OrRd', legend=True, legend_kwds={"label": "SO2", "orientation": "horizontal"},vmin = mindata["SO2"],vmax = maxdata["SO2"])
#         SeoulGeo_pollution2019.plot(ax=axes[0][2], column='PM2.5', cmap='OrRd', legend=True, legend_kwds={"label": "", "orientation": "horizontal"},vmin = mindata["PM2.5"],vmax = maxdata["PM2.5"])
#         SeoulGeo_pollution2019.plot(ax=axes[1][2], column='PM10', cmap='OrRd', legend=True, legend_kwds={"label": "", "orientation": "horizontal"},vmin = mindata["PM10"],vmax = maxdata["PM10"])
#         SeoulGeo_pollution2019.plot(ax=axes[2][2], column='CO', cmap='OrRd', legend=True, legend_kwds={"label": "", "orientation": "horizontal"},vmin = mindata["CO"],vmax = maxdata["CO"])
#         SeoulGeo_pollution2019.plot(ax=axes[3][2], column='SO2', cmap='OrRd', legend=True, legend_kwds={"label": "", "orientation": "horizontal"},vmin = mindata["SO2"],vmax = maxdata["SO2"])

#         for i, ax_row in enumerate(axes):
#             for j, ax in enumerate(ax_row):
#                 ax.set_xticks([])
#                 ax.set_yticks([])
#                 if i ==0:
#                     if j == 0:
#                         ax.set_title("2017" , fontsize=12)
#                     elif j==1:
#                         ax.set_title("2018" , fontsize=12)
#                     else:
#                         ax.set_title("2019" , fontsize=12)
#                 else:
#                     ax.set_title(" ")
#         plt.savefig("/opt/airflow/dags/geo_map.png")


# def _correlation_plot():
#         import pandas as pd 
#         import seaborn as sns
#         import matplotlib.pyplot as plt
#         import numpy as np
#         from pyspark.sql import SparkSession
#         from pyspark.sql.functions import col, split, trim, substring 

#         spark = SparkSession.builder.appName('corelation_analysis').getOrCreate() 
#         Seoul = spark.read.format("csv").option("header", "true").load("/opt/airflow/dags/AirPollutionSeoul/Seoul_MY").drop("Latitude","Longitude","Station code")


#         Seoul = Seoul.withColumn("M", substring("Measurement date", 6, 2).cast("int"))
#         Seoul = Seoul.withColumn("Y", substring("Measurement date", 1, 4).cast("int"))
#         Seoul= Seoul.drop("Measurement date")

#         pre_plot =  Seoul.drop("Y").groupby(["Address","M"]).mean()
#         plot_temp= pre_plot.drop("Address","M")
#         fig1 = plt.figure(figsize=(12,5))
#         corr= plot_temp.corr()
#         matrix = np.triu(corr)
#         cmap = sns.diverging_palette(230, 20, as_cmap=True)
#         sns.heatmap(corr,annot=True, mask=matrix, cmap=cmap)
#         plt.savefig("/opt/airflow/dags/correlation1.png")

#         fig,axes = plt.subplots(figsize=(6, 6), ncols=2, nrows=3,layout="compressed")
#         sns.regplot(x="PM2.5",y="PM10",data = plot_temp, ax=axes[0,0],line_kws={"color": "red"})
#         sns.residplot(x="PM2.5",y="PM10",data = plot_temp, ax=axes[0,1])
#         sns.regplot(x="O3",y="CO",data = plot_temp, ax=axes[1,0],line_kws={"color": "red"})
#         sns.residplot(x="O3",y="CO",data = plot_temp, ax=axes[1,1])
#         sns.regplot(x="O3",y="SO2",data = plot_temp, ax=axes[2,0],line_kws={"color": "red"})
#         sns.residplot(x="O3",y="SO2",data = plot_temp, ax=axes[2,1])
#         plt.savefig("/opt/airflow/dags/correlation2.png")

def _correlation_plot():
        import seaborn as sns
        import numpy as np
        import os
        import matplotlib.pyplot as plt
        from pyspark.sql import SparkSession
        import pyspark.pandas as ps

        spark = SparkSession.builder.appName('spark').getOrCreate()

# Load data from CSV files into Spark DataFrames
        Seoul_all = spark.read.format("csv").option("header", "true").load("/opt/airflow/dags/AirPollutionSeoul/Seoul_MY")
        pollution_columns = ['SO2', 'NO2', 'O3', 'CO', 'PM10', 'PM25']
        for col in pollution_columns:
            Seoul_all = Seoul_all.withColumn(col, Seoul_all[col].cast('float'))
            
        Seoul_all = Seoul_all.toPandas()
        Seoul_all = Seoul_all.drop(["Latitude","Longitude","Station code"],axis=1)
        Seoul_all.insert(0,"M",Seoul_all["Measurement date"].str.slice(5,7),True)
        Seoul_all.insert(1,"Y",Seoul_all["Measurement date"].str.slice(0,4),True)
        Seoul_all.drop("Measurement date",axis=1,inplace=True)
        pre_plot = Seoul_all.drop(["Y"],axis=1).groupby(["Address","M"],as_index = False).mean()

        plot_temp= pre_plot.drop(["Address","M"],axis=1)
        fig1 = plt.figure(figsize=(12,5))
        corr= plot_temp.corr()
        matrix = np.triu(corr)
        cmap = sns.diverging_palette(230, 20, as_cmap=True)
        sns.heatmap(corr,annot=True, mask=matrix, cmap=cmap)
        plt.savefig("/opt/airflow/dags/correlation1.png")

        fig,axes = plt.subplots(figsize=(6, 6), ncols=2, nrows=3,layout="compressed")
        sns.regplot(x="PM25",y="PM10",data = plot_temp, ax=axes[0,0],line_kws={"color": "red"})
        sns.residplot(x="PM25",y="PM10",data = plot_temp, ax=axes[0,1])
        sns.regplot(x="O3",y="CO",data = plot_temp, ax=axes[1,0],line_kws={"color": "red"})
        sns.residplot(x="O3",y="CO",data = plot_temp, ax=axes[1,1])
        sns.regplot(x="O3",y="SO2",data = plot_temp, ax=axes[2,0],line_kws={"color": "red"})
        sns.residplot(x="O3",y="SO2",data = plot_temp, ax=axes[2,1])
        plt.savefig("/opt/airflow/dags/correlation2.png")

with DAG(
    "Spark",
    start_date= timezone.datetime(2024, 8, 24),  # Start the DAG one day ago, to make it immediately available
    schedule_interval=None,  # No schedule, manual or trigger-based execution
    tags=["kaggle"],  # Tags for organizing DAGs in the UI
):

    start = EmptyOperator(
        task_id = "start"
    )

    download_dataset_pollution_api = BashOperator(
    task_id="download_dataset_pollution_api",
    bash_command=(
       "kaggle datasets download -d bappekim/air-pollution-in-seoul -p /opt/airflow/dags --unzip"
    ),
    )

    download_dataset_bike_api = BashOperator(
        task_id = 'download_dataset_bike_api',
        bash_command = (
            "kaggle datasets download -d saurabhshahane/seoul-bike-sharing-demand-prediction -p /opt/airflow/dags --unzip"
        ) 
    )

    geo_map_plot = PythonOperator(
        task_id = "geo_map_plot",
        python_callable = _geomerge_plot,
    )

    get_seoul_api_realtime = PythonOperator(
        task_id = "get_seoul_api",
        python_callable = _get_seoul_api,
    )
    spark_clean = PythonOperator(
         task_id = "spark_clean",
         python_callable = _sqlspark_data_refining
    )

    correlation_plot = PythonOperator(
         task_id = "correlation_plot",
         python_callable = _correlation_plot,
    )

    stop = EmptyOperator(
        task_id = "stop"
    )


    start >> download_dataset_pollution_api >> spark_clean  
    start >> download_dataset_bike_api >> spark_clean
    spark_clean >> geo_map_plot >> stop
    spark_clean >> correlation_plot >> stop
    get_seoul_api_realtime >> stop 
    

