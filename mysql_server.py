import base64
from io import BytesIO
import json
from matplotlib import pyplot as plt
import mysql.connector
import logging
import sys
from mcp.server.fastmcp import FastMCP
from datetime import datetime, date
from typing import Dict, List, Any, Optional

import pandas as pd



logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)

logger = logging.getLogger('mysql_mcp_server')


DB_CONFIG = {

}

server = FastMCP(name="mysql-server", description="MySQL数据库交互服务器")

def get_db_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as err:
        logger.error(f"Error connecting to database: {err}")
        return None


def json_serialize(obj):
    if isinstance(obj,(datetime,date)):
        return obj.isoformat()
    elif hasattr(obj,"decimal") or str(type(obj)) == "<class 'decimal.Decimal'>":
        return float(obj)
    raise TypeError(f"Type {type(obj)} is not serializable")


@server.tool()

async def execute_query(query:str) -> Dict[str,Any]:
    """执行SQL查询并返回结果
    
    Args:
        query: SQL查询语句
        
    Returns:
        查询结果
    """
    try:
        logger.info(f"Executing query: {query}")
        conn = get_db_connection()
        if not conn:
            return {"error": "Failed to connect to the database"}
            
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query)

        if query.strip().upper().startswith(("SELECT","SHOW","DESCRIBE","EXPLAIN")):
            results = cursor.fetchall()
            try:
                serializeable_results = json.loads(
                    json.dumps(results[:1000],default=json_serialize)
                )
                return {
                    "success": True,
                    "query_type": query.strip().upper().split()[0],
                    "row_count": len(results),
                    "results": serializeable_results
                }
            except Exception as e:
                logger.error(f"Error serializing results: {e}")
                return {"error": "Failed to serialize results"}
        else:
            conn.commit()
            return {
                "success": True,
                "query_type": query.strip().upper().split()[0],
                "row_count": cursor.rowcount,
                "affected_rows": cursor.rowcount
            }
    except mysql.connector.Error as err:
        logger.error(f"Database error executing query: {err}")
        return {"error": str(err)}
    finally:
        cursor.close()
        conn.close()

@server.tool()
async def get_tables() -> Dict[str,Any]:
    """获取数据库中的所有表
    
    Returns:
        表列表及其行数和结构
    """
    try:
            
        results = await execute_query("SHOW TABLES")
        if "error" in results:
            return results
        
        tables = []
        for table_row in results["results"]:
            # table name
            table_name = list(table_row.values())[0]

            # table row count
            count_result = await execute_query(f"SELECT COUNT(*) as count FROM {table_name}")
            row_count = 0
            if "error" not in count_result and count_result["results"]:
                row_count = count_result["results"][0]["count"]

            # table structure
            structure_result = await execute_query(f"DESCRIBE {table_name}")
            structure = structure_result.get("results",[]) if "error" not in structure_result else []

            try:
                serializable_structure = json.loads(
                    json.dumps(structure,default=json_serialize)
                )
                tables.append({
                    "table_name": table_name,
                    "row_count": row_count,
                    "structure": serializable_structure
                })
            except Exception as e:
                logger.error(f"Error serializing structure for table {table_name}: {e}")
                return {"error": str(e)}

        return {
            "success": True,
            "database": DB_CONFIG["database"],
            "table_count": len(tables),
            "tables": tables
        }
    except Exception as e:
        logger.error(f"Error getting tables: {e}")
        return {"error": str(e)}


@server.tool()
async def get_table_columns(table_name:str) -> Dict[str,Any]:
    """获取指定表的列信息
    
    Args:
        table_name: 表名
        
    Returns:
        表列信息
    """
    try:
        structure_results = await execute_query(f"DESCRIBE {table_name}")
        structure = structure_results.get("results",[]) if "error" not in structure_results else []

        columns = []
        try:
            serialize_structure = json.loads(
                json.dumps(structure,default=json_serialize)
            )
            
            for column in serialize_structure:
                columns.append(column["Filed"])

        except Exception as e:
            return {"error": str(e)}
        

        return {
            "success":True,
            "table_name":table_name,
            "column_count":len(columns),
            "columns":columns
        }
    
    except Exception as e:
        return {"error":str(e)}

@server.tool()
async def visualize_data(query:str,x_column:str,y_column:str,chart_type:str="bar") -> Dict[str,Any]:
    """执行查询并可视化结果
    
    Args:
        query: SQL查询语句
        x_column: X轴列名
        y_column: Y轴列名
        chart_type: 图表类型 (bar, line, scatter, pie)
        
    Returns:
        包含Base64编码图表的结果
    """


    try:
        query_results = await execute_query(query)
        if "error" in query_results:
            return query_results
        
        results = query_results["results"]
        if not results:
            return {"error":"No results found"}

        # 将查询结果转换为Pandas DataFrame
        df = pd.DataFrame(results)

        # 确保x_column和y_column是DataFrame中的列
        if x_column not in df.columns or y_column not in df.columns:
            return {"error":"Invalid column names"}
        
        plt.figure(figsize=(10,6))

        # 根据chart_type生成图表
        if chart_type == "bar":
            # 生成柱状图
            plt.bar(df[x_column],df[y_column])
        elif chart_type == "line":
            # 生成折线图
            plt.plot(df[x_column],df[y_column])
        elif chart_type == "pie":
            # 生成饼图
            plt.pie(df[y_column],labels=df[x_column],autopct="%1.1f%%")
        else:
            return {"error":"Invalid chart type"}
        
        plt.xlabel(x_column)
        plt.ylabel(y_column)
        plt.tight_layout()
        
        # 将图表转换为base64
        buffer = BytesIO()
        plt.savefig(buffer,format="png")
        buffer.seek(0)
        chart_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        plt.close()
        
        return {
            "success":True,
            "chart_base64":chart_base64
        }
        
    except Exception as e:
        return {"error":str(e)}



# ======= 提示模板 =======

@server.prompt()
def sql_query_builder() -> str:
    """SQL查询构建器提示模板"""
    return """
请帮我构建一个SQL查询来从数据库中检索信息。

数据库当前包含以下表:
{tables_info}

我需要一个查询来解决以下问题:
{problem_description}

请提供完整的SQL查询,并解释查询的每个部分。
"""

@server.prompt()
def data_analysis_report() -> str:
    """数据分析报告生成提示模板"""
    return """
请基于以下数据生成一份详细的分析报告:

```
{data}
```

报告应包括:
1. 数据概述和主要指标
2. 关键趋势和模式分析
3. 异常值和特殊情况识别
4. 业务洞察和建议

请使用专业的语言和格式，使报告易于理解和实用。
"""


@server.resource("mysql://schema/{table}")
async def get_table_schema(table: str) -> str:
    """获取表结构"""
    try:
        structure_result = await execute_query(f"DESCRIBE `{table}`")
        if "error" in structure_result:
            return f"Error: {structure_result['error']}"
            
        structure = structure_result.get("results", [])
        return json.dumps(structure, default=json_serialize, indent=2)
    except Exception as e:
        return f"Error: {str(e)}"


@server.resource("mysql://data/{table}")
async def get_table_data(table: str) -> str:
    """获取表数据"""
    try:
        data_result = await execute_query(f"SELECT * FROM `{table}` LIMIT 50")
        if "error" in data_result:
            return f"Error: {data_result['error']}"
            
        data = data_result.get("results", [])
        return json.dumps(data, default=json_serialize, indent=2)
    except Exception as e:
        return f"Error: {str(e)}"


@server.resource("mysql://info")
async def get_database_info() -> str:
    """获取数据库信息"""
    try:
        # 获取数据库版本
        version_result = await execute_query("SELECT VERSION() as version")
        if "error" in version_result:
            return f"Error: {version_result['error']}"
            
        version = version_result.get("results", [{}])[0].get("version", "Unknown")
        
        # 获取数据库状态
        status_result = await execute_query("SHOW STATUS")
        if "error" in status_result:
            status = []
        else:
            status = status_result.get("results", [])
            
        # 获取所有表
        tables_info = await get_tables()
        if "error" in tables_info:
            tables = []
        else:
            tables = tables_info.get("tables", [])
            
        info = {
            "database": DB_CONFIG["database"],
            "version": version,
            "host": DB_CONFIG["host"],
            "tables": [table["table_name"] for table in tables],
            "table_count": len(tables)
        }
        
        return json.dumps(info, default=json_serialize, indent=2)
    except Exception as e:
        return f"Error: {str(e)}"

# 启动服务器
if __name__ == "__main__":
    logger.info("启动MySQL数据库MCP服务器...")
    logger.info(f"数据库配置: {DB_CONFIG}")
    logger.info("使用stdio传输方式")
    
    try:
        server.run(transport='stdio')
    except Exception as e:
        logger.error(f"服务器运行失败: {str(e)}")
        sys.exit(1)
