# Databricks notebook source
#Import Spark Session
from pyspark.sql import SparkSession
from pyspark.sql import Row
from pyspark.sql.types import *
from pyspark.sql.functions import *


# COMMAND ----------

# Build the SparkSession
spark=SparkSession.builder.master('local').appName("Sessionize IP addresses").getOrCreate()
sc = spark.sparkContext

# COMMAND ----------

#load data by creating rdd
filepathpath = 'dbfs:/FileStore/shared_uploads/rajaram.sahu@mindteck.com/2015_07_22_mktplace_shop_web_log_sample_log.gz'
rdd = sc.textFile(filepathpath)
#split the data @ empty spaces
rdd = rdd.map(lambda line: line.split(" "))

# COMMAND ----------


# ====================================
# Transforming Raw data 
# ====================================

# COMMAND ----------

#Map the RDD to a DF for better performance
mainDF = rdd.map(lambda line: Row(timestamp=line[0], ipaddress=line[2].split(':')[0],url=line[12])).toDF()
mainDF.show(20)

# COMMAND ----------

# convert timestamps from string to timestamp datatype
mainDF = mainDF.withColumn('timestamp', mainDF['timestamp'].cast(TimestampType()))

# COMMAND ----------

# sessionizing data based on 15 min fixed window time
# assign an Id to each session
SessionDF = mainDF.select(window("timestamp", "15 minutes").alias('FixedTimeWindow'),'timestamp',"ipaddress").groupBy('FixedTimeWindow','ipaddress').count().withColumnRenamed('count', 'NumberHitsInSessionForIp')
SessionDF = SessionDF.withColumn("SessionId", monotonically_increasing_id())
SessionDF.show(20,False)

# COMMAND ----------

# join the time stamps and url to the Sessionized DF
dfWithTimeStamps = mainDF.select(window("timestamp", "15 minutes").alias('FixedTimeWindow'),'timestamp',"ipaddress","url")
SessionDF = dfWithTimeStamps.join(SessionDF,['FixedTimeWindow','ipaddress'])
SessionDF.show(20)

# COMMAND ----------

# Finding the first hit time of each ip for each session and join in to our session df
FirstHitTimeStamps = SessionDF.groupBy("SessionId").agg(min("timestamp").alias('FristHitTime'))
SessionDF = FirstHitTimeStamps.join(SessionDF,['SessionId'])
SessionDF.select(col("SessionId"),col("ipaddress"),col("FristHitTime")).show(20)

# COMMAND ----------

#2. Determine the average session time
# Among all the hits in a session the last one has the max diff with first hit
# we define the time difference of first and last hit in a session to be the duration of a session for an ip
# if there is only one hit in a session the duration is zero
timeDiff = (unix_timestamp(SessionDF.timestamp)-unix_timestamp(SessionDF.FristHitTime))
SessionDF = SessionDF.withColumn("timeDiffwithFirstHit", timeDiff)
tmpdf = SessionDF.groupBy("SessionId").agg(max("timeDiffwithFirstHit").alias("SessionDuration"))
SessionDF = SessionDF.join(tmpdf,['SessionId'])
SessionDF.select(col("SessionId"),col("ipaddress"),col("SessionDuration")).show(20)

# COMMAND ----------

#3. Determine unique URL visits per session. To clarify, count a hit to a unique URL only once per session
dfURL = SessionDF.groupBy("SessionId","URL").count().distinct().withColumnRenamed('count', 'hitURLcount')
dfURL.show(20)

# COMMAND ----------

#4. Find the most engaged users, ie the IPs with the longest session times
EngagedUsers = SessionDF.select("ipaddress","SessionID","SessionDuration").sort(col("SessionDuration").desc()).distinct()
EngagedUsers.show(2)

# COMMAND ----------

# showing the mean session duration
# the printed number is secconds
meandf = SessionDF.groupBy().avg('SessionDuration')
meandf.show()
