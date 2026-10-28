import sys
sys.path.append(r'C:\Users\William Ordiales\OneDrive\Documentos\propelling_datachellenge\_modules')
from snowflake_client import SnowflakeClient
# credentials are read (encrypted) from _credentials/ - see _modules/cripto.py


"""" aprodundando analisis de la tabla customer"""
sf = SnowflakeClient(target="dev", layer="bronze")
sf.connect()

result = sf.query("select *  from brz_customer")
df = sf.to_pandas(result)
sf.close()
df.describe()
df.dtypes
df.columns
len(df["c_custkey"].unique())
len(df["_batch_id"].unique())
len(df["c_mktsegment"].unique())
df["c_mktsegment"].unique()
df.drop_duplicates().shape

"""" aprodundando analisis de la tabla lineitem"""
sf = SnowflakeClient(target="dev", layer="bronze")
sf.connect()

result = sf.query("select * from brz_lineitem limit 100000")
df = sf.to_pandas(result)
sf.close()
df.describe()
df.dtypes
df.columns
df.head(5)
len(df["l_orderkey"].unique())
len(df["l_partkey"].unique())
len(df["l_suppkey"].unique())
df["l_linenumber"].unique()
df.drop_duplicates().shape

len(df[["l_orderkey","l_partkey","l_suppkey","l_shipdate"]].drop_duplicates())

result_fecha = sf.query("select distinct max(l_shipdate) as fecha_max, min(l_shipdate) as fecha_min from brz_lineitem")
df_fecha = sf.to_pandas(result_fecha)

"""" aprodundando analisis de la tabla nation"""
sf = SnowflakeClient(target="dev", layer="bronze")
sf.connect()

result = sf.query("select * from brz_nation")
df = sf.to_pandas(result)
sf.close()
df.describe()
df.dtypes
df.columns
df.head(5)
df.shape
len(df["n_nationkey"].unique())
len(df["n_regionkey"].unique())
df["n_name"].unique()
df.drop_duplicates().shape

"""" aprodundando analisis de la tabla oders"""
sf = SnowflakeClient(target="dev", layer="bronze")
sf.connect()

result = sf.query("select * from brz_orders")
df = sf.to_pandas(result)
sf.close()
df.describe()
df.dtypes
df.columns
df.head(5)
df.shape
len(df["o_orderkey"].unique())
len(df["o_custkey"].unique())
df.drop_duplicates().shape

result_fecha = sf.query("select distinct max(o_orderdate) as fecha_max, min(o_orderdate) as fecha_min from brz_orders")
df_fecha = sf.to_pandas(result_fecha)

"""" aprodundando analisis de la tabla part"""
sf = SnowflakeClient(target="dev", layer="bronze")
sf.connect()

result = sf.query("select * from brz_part")
df = sf.to_pandas(result)
sf.close()
df.describe()
df.dtypes
df.columns
df.head(5)
df.shape
len(df["p_partkey"].unique())
len(df["p_name"].unique())
len(df["_batch_id"].unique())
df.drop_duplicates().shape

"""" aprodundando analisis de la tabla partspp"""
sf = SnowflakeClient(target="dev", layer="bronze")
sf.connect()

result = sf.query("select * from brz_partsupp limit 1000")
result = sf.query("select count(*) from brz_partsupp") #800000
result = sf.query("select distinct count(ps_partkey) from brz_partsupp") #800000
result = sf.query("select distinct count(ps_suppkey) from brz_partsupp") #800000
result = sf.query("select distinct count(*) from brz_partsupp") #800000
df = sf.to_pandas(result)
sf.close()

"""" aprodundando analisis de la tabla region"""
sf = SnowflakeClient(target="dev", layer="bronze")
sf.connect()

result = sf.query("select * from brz_region")
df = sf.to_pandas(result)
sf.close()

df.shape
df["r_name"].unique()
len(df["r_regionkey"].unique())

"""" aprodundando analisis de la tabla region"""
sf = SnowflakeClient(target="dev", layer="bronze")
sf.connect()

result = sf.query("select * from brz_supplier")
df = sf.to_pandas(result)
sf.close()

df.shape
df.describe()
df.dtypes
df.head(5)
len(df["s_suppkey"].unique())
len(df["s_nationkey"].unique())





