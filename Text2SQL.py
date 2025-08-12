import json
import re
import pandas as pd
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.runnables import RunnablePassthrough
from langchain_community.utilities import SQLDatabase
from langchain_core.output_parsers import StrOutputParser
from sqlalchemy import create_engine, text
import os
import sys
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

@dataclass
class DatabaseConfig:
    """Database configuration"""
    host: str = "localhost"
    port: int = 3306
    user: str = "root"
    password: str = "123"
    database: str = "SchoolDB"
    
    @property
    def uri(self) -> str:
        return f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

@dataclass
class UserInfo:
    """User information"""
    user_id: str
    role: str  # 'student' or 'teacher'
    role_id: int
    
class DatabaseManager:
    """Manages database connections and operations"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.engine = None
        self.db = None
        self._connect()
    
    def _connect(self):
        """Establish database connection"""
        try:
            self.engine = create_engine(self.config.uri)
            self.db = SQLDatabase.from_uri(self.config.uri)
            print("Kết nối cơ sở dữ liệu thành công!")
        except Exception as e:
            print(f"Lỗi kết nối cơ sở dữ liệu: {e}")
            sys.exit(1)
    
    def execute_query(self, query: str) -> pd.DataFrame:
        """Execute SQL query and return results"""
        try:
            with self.engine.connect() as connection:
                with connection.begin():
                    query_lower = query.lower().strip()
                    if query_lower.startswith('select'):
                        result = pd.read_sql(query, connection)
                        return result
                    else:
                        result = connection.execute(text(query))
                        print(f"Đã thực thi {query_lower.split()[0].upper()}: {result.rowcount} hàng bị ảnh hưởng.")
                        return pd.DataFrame({"result": ["Thực thi thành công."]})
        except Exception as e:
            print(f"Lỗi khi thực thi truy vấn: {e}")
            return pd.DataFrame({"error": [str(e)]})
    
    def get_schema(self) -> str:
        """Get database schema information"""
        return self.db.get_table_info()
    
    def get_table_columns(self, table_name: str) -> List[str]:
        """Get all columns of a table"""
        try:
            with self.engine.connect() as connection:
                query = f"SHOW COLUMNS FROM {table_name}"
                result = pd.read_sql(query, connection)
                return result['Field'].tolist()
        except Exception as e:
            print(f"Lỗi khi lấy cột của bảng {table_name}: {e}")
            return []
    
    def get_user_info(self, user_id: str) -> Optional[UserInfo]:
        """Determine user role and get role_id from user_id"""
        try:
            with self.engine.connect() as connection:
                # Check if user is a student
                student_query = "SELECT StudentID FROM Students WHERE UserID = %s"
                student_result = pd.read_sql(student_query, connection, params=(user_id,))
                
                if not student_result.empty:
                    return UserInfo(user_id, "student", student_result.iloc[0, 0])
                
                # Check if user is a teacher
                teacher_query = "SELECT TeacherID FROM Teachers WHERE UserID = %s"
                teacher_result = pd.read_sql(teacher_query, connection, params=(user_id,))
                
                if not teacher_result.empty:
                    return UserInfo(user_id, "teacher", teacher_result.iloc[0, 0])
                
                return None
        except Exception as e:
            print(f"Lỗi khi xác định thông tin người dùng: {e}")
            return None

class SQLParserLLM:
    """LLM-based SQL parser for better accuracy"""
    
    def __init__(self, llm):
        self.llm = llm
        self.parser_prompt = ChatPromptTemplate.from_template("""
Bạn là một chuyên gia phân tích SQL. Hãy phân tích câu truy vấn SQL sau và trả về thông tin dưới dạng JSON với cấu trúc:

{{
    "operation": "SELECT/INSERT/UPDATE/DELETE",
    "tables": ["table1", "table2", ...],
    "columns_by_table": {{
        "table1": ["column1", "column2", ...],
        "table2": ["column3", "column4", ...]
    }}
}}

QUY TẮC:
1. "operation": Chỉ trả về một trong SELECT, INSERT, UPDATE, DELETE
2. "tables": Danh sách tất cả bảng được sử dụng (FROM, JOIN, INTO, UPDATE)
3. "columns_by_table": Chỉ liệt kê các cột cụ thể được truy vấn/cập nhật, không bao gồm '*'
4. Nếu SELECT *, không liệt kê columns_by_table cho bảng đó
5. Tên bảng và cột giữ nguyên case như trong SQL
6. Chỉ trả về JSON thuần túy, không có markdown hay text khác

SQL Query: {query}
""")
    
    def parse_sql_with_llm(self, query: str) -> Dict:
        """Parse SQL using LLM for better accuracy"""
        try:
            chain = self.parser_prompt | self.llm | StrOutputParser()
            result = chain.invoke({"query": query})
            
            # Clean up markdown formatting if present
            if result.startswith('```json'):
                result = result[7:]
            elif result.startswith('```'):
                result = result[3:]
            if result.endswith('```'):
                result = result[:-3]
            
            result = result.strip()
            
            # Parse JSON
            parsed_result = json.loads(result)
            
            # Validate structure
            if not all(key in parsed_result for key in ["operation", "tables", "columns_by_table"]):
                raise ValueError("Missing required keys in parsed result")
            
            return parsed_result
            
        except (json.JSONDecodeError, Exception) as e:
            print(f"LLM parsing failed, falling back to regex: {e}")
            # Fallback to regex parsing
            return self._fallback_regex_parse(query)
    
    def _fallback_regex_parse(self, query: str) -> Dict:
        """Fallback regex parsing method"""
        query_lower = query.lower().strip()
        
        # Determine operation
        operation = None
        for op in ["SELECT", "INSERT", "UPDATE", "DELETE"]:
            if query_lower.startswith(op.lower()):
                operation = op
                break
        
        # Find tables
        tables = []
        table_patterns = [
            r'\bfrom\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'\bjoin\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'\binto\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'\bupdate\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        ]
        
        for pattern in table_patterns:
            matches = re.findall(pattern, query_lower, re.IGNORECASE)
            tables.extend(matches)
        
        # Remove duplicates and capitalize
        tables = list(set([t.capitalize() for t in tables]))
        
        # Find columns (basic regex approach)
        columns_by_table = {}
        
        if operation == "SELECT":
            select_match = re.search(r'select\s+(.*?)\s+from', query_lower, re.IGNORECASE | re.DOTALL)
            if select_match:
                select_part = select_match.group(1)
                columns = []
                for col in select_part.split(','):
                    col = col.strip()
                    # Skip if it's SELECT *
                    if col == '*':
                        continue
                    # Remove DISTINCT, functions
                    col = re.sub(r'^(distinct\s+)', '', col, flags=re.IGNORECASE)
                    # Handle table.column format
                    if '.' in col:
                        table_part, col_part = col.split('.', 1)
                        table_name = table_part.strip().capitalize()
                        col_name = col_part.strip()
                        if table_name not in columns_by_table:
                            columns_by_table[table_name] = []
                        columns_by_table[table_name].append(col_name)
                    else:
                        columns.append(col.strip())
                
                # If no table-specific columns found, assign to first table
                if columns and tables and not columns_by_table:
                    columns_by_table[tables[0]] = columns
        
        return {
            "operation": operation,
            "tables": tables,
            "columns_by_table": columns_by_table
        }

class PermissionManager:
    """Manages user permissions with enhanced LLM-based parsing"""
    
    def __init__(self, config_file: str = "permissions2.json", llm=None):
        self.permissions = self._load_permissions(config_file)
        self.sql_parser = SQLParserLLM(llm) if llm else None
        
    def _load_permissions(self, config_file: str) -> Dict:
        """Load permissions configuration"""
        try:
            with open(config_file, 'r', encoding='utf-8') as file:
                return json.load(file)
        except Exception as e:
            print(f"Lỗi khi đọc tệp cấu hình quyền: {e}")
            return {"roles": {}}
    
    def parse_sql_query(self, query: str) -> Dict:
        """Parse SQL query using LLM or fallback to regex"""
        if self.sql_parser:
            return self.sql_parser.parse_sql_with_llm(query)
        else:
            return self.sql_parser._fallback_regex_parse(query) if self.sql_parser else self._basic_regex_parse(query)
    
    def _basic_regex_parse(self, query: str) -> Dict:
        """Basic regex parsing when LLM is not available"""
        query_lower = query.lower().strip()
        
        # Determine operation
        operation = None
        for op in ["SELECT", "INSERT", "UPDATE", "DELETE"]:
            if query_lower.startswith(op.lower()):
                operation = op
                break
        
        # Find tables
        tables = []
        table_patterns = [
            r'\bfrom\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'\bjoin\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'\binto\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'\bupdate\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        ]
        
        for pattern in table_patterns:
            matches = re.findall(pattern, query_lower, re.IGNORECASE)
            tables.extend(matches)
        
        # Remove duplicates and capitalize
        tables = list(set([t.capitalize() for t in tables]))
        
        return {
            "operation": operation,
            "tables": tables,
            "columns_by_table": {}
        }
    
    def check_permissions(self, query: str, user_role: str, db_manager: DatabaseManager) -> bool:
        """Check if user has permission to execute the query"""
        if user_role not in self.permissions["roles"]:
            raise ValueError(f"Vai trò '{user_role}' không được định nghĩa trong cấu hình.")

        role_config = self.permissions["roles"][user_role]
        table_permissions = role_config.get("table_permissions", {})

        # Check for Users table access
        if 'users' in query.lower():
            raise ValueError("Truy vấn không được phép truy cập bảng 'Users'")

        # Parse query with enhanced method
        try:
            parsed_info = self.parse_sql_query(query)
            operation = parsed_info.get("operation")
            tables = parsed_info.get("tables", [])
            columns_by_table = parsed_info.get("columns_by_table", {})
        except Exception as e:
            print(f"Warning: Failed to parse query with enhanced method: {e}")
            # Use basic fallback
            parsed_info = self._basic_regex_parse(query)
            operation = parsed_info.get("operation")
            tables = parsed_info.get("tables", [])
            columns_by_table = {}

        if not operation:
            raise ValueError("Không xác định được thao tác SQL")

        print(f"Debug - Parsed: Operation={operation}, Tables={tables}, Columns={columns_by_table}")

        # Check permissions for each table
        for table in tables:
            table_key = next((t for t in table_permissions if t.lower() == table.lower()), None)
            
            if table_key is None and "*" not in table_permissions:
                raise ValueError(f"Vai trò '{user_role}' không được phép truy vấn bảng '{table}'")

            if table_key:
                allowed_operations = table_permissions[table_key].get("allowed_operations", [])
                allowed_columns = table_permissions[table_key].get("allowed_columns", [])
            else:
                allowed_operations = table_permissions["*"].get("allowed_operations", [])
                allowed_columns = table_permissions["*"].get("allowed_columns", [])

            if operation not in allowed_operations:
                raise ValueError(f"Vai trò '{user_role}' không được phép thực hiện '{operation}' trên bảng '{table}'")

            # Check column permissions (enhanced with LLM parsing)
            if allowed_columns and operation in ["SELECT", "UPDATE"]:
                columns_for_table = columns_by_table.get(table, [])
                
                # If LLM parsing worked and we have specific columns
                if columns_for_table:
                    for col in columns_for_table:
                        # Skip wildcard and function results
                        if col == '*' or '(' in col:
                            continue
                        if not any(col.lower() == allowed_col.lower() for allowed_col in allowed_columns):
                            raise ValueError(f"Vai trò '{user_role}' không được phép truy vấn cột '{col}' trong bảng '{table}'")
                # If no specific columns found but we have SELECT *, check if * is allowed
                elif operation == "SELECT" and not columns_for_table:
                    # This might be SELECT * case, we'll allow it if the role has general access
                    pass

        return True

class SQLTemplateManager:
    """Manages SQL query templates for different roles"""
    
    @staticmethod
    def create_template(user_role: str, role_id: int) -> str:
        """Create role-specific template"""
        
        base_template = """
Dựa trên schema bảng dưới đây, viết một câu truy vấn SQL thuần túy để trả về câu trả lời cho câu hỏi.
Chỉ trả về MỘT câu truy vấn SQL duy nhất, không thêm định dạng Markdown, ký tự xuống dòng thừa, hoặc văn bản giải thích.
Tên bảng và cột phải chính xác như trong schema.
Không sử dụng bí danh bảng trừ khi cần thiết cho JOIN.
Không được truy vấn bảng Users hoặc cột UserID.
"""

        if user_role.lower() == "student":
            role_specific = f"""
BẠN LÀ SINH VIÊN với StudentID = {role_id}.

QUY TẮC BẮT BUỘC:
- Luôn thêm điều kiện StudentID = {role_id} khi truy vấn Students
- Khi truy vấn Classes, Courses, Schedules: chỉ lấy những lớp đã đăng ký thông qua Enrollments
- Khi truy vấn Teachers: chỉ lấy giảng viên dạy lớp mình học
- "thông tin của tôi" = SELECT StudentID, StudentCode, DateOfBirth, FullName, Email, PhoneNumber, Major, EnrollmentDate FROM Students WHERE StudentID = {role_id}
- "lớp học đã đăng ký" = JOIN với Enrollments WHERE Enrollments.StudentID = {role_id}

VÍ DỤ:
- Câu hỏi: "các lớp học tôi đã đăng ký"
  SQL: SELECT Courses.CourseName, Courses.CourseCode, Classes.Semester, Classes.AcademicYear, Enrollments.Status FROM Enrollments JOIN Classes ON Enrollments.ClassID = Classes.ClassID JOIN Courses ON Classes.CourseID = Courses.CourseID WHERE Enrollments.StudentID = {role_id}
"""
        else:  # teacher
            role_specific = f"""
BẠN LÀ GIẢNG VIÊN với TeacherID = {role_id}.

QUY TẮC BẮT BUỘC:
- Luôn thêm điều kiện TeacherID = {role_id} khi truy vấn Teachers
- Khi truy vấn Classes: WHERE TeacherID = {role_id}
- Khi truy vấn Students: JOIN với Classes và Enrollments WHERE Classes.TeacherID = {role_id}
- "thông tin của tôi" = SELECT TeacherID, FullName, Email, PhoneNumber, TeacherCode, Department, HireDate FROM Teachers WHERE TeacherID = {role_id}
"""

        template = base_template + role_specific + """
{schema}

Câu hỏi: {question}
Câu truy vấn SQL:"""
        
        return template

class QueryProcessor:
    """Main query processing class with enhanced SQL parsing"""
    
    def __init__(self, api_key: str):
        os.environ["GOOGLE_API_KEY"] = api_key
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-pro", 
            google_api_key=api_key,
            temperature=0
        )
        self.db_manager = DatabaseManager(DatabaseConfig())
        # Pass LLM to PermissionManager for enhanced parsing
        self.permission_manager = PermissionManager(llm=self.llm)
        
    def create_chain(self, user_info: UserInfo):
        """Create SQL processing chain"""
        template = SQLTemplateManager.create_template(user_info.role, user_info.role_id)
        prompt = ChatPromptTemplate.from_template(template)
        
        chain = (
            RunnablePassthrough.assign(schema=lambda _: self.db_manager.get_schema())
            | prompt 
            | self.llm.bind(stop=["\nSQL Result:", "SQL Result:", "\n\n", ";"])
            | StrOutputParser()
        )
        
        return chain
    
    def clean_query(self, query: str) -> str:
        """Clean and normalize SQL query"""
        if not query or not query.strip():
            return ""
            
        cleaned = query.strip()
        
        # Remove markdown formatting
        if cleaned.startswith('```sql'):
            cleaned = cleaned[6:]
        elif cleaned.startswith('```'):
            cleaned = cleaned[3:]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
        
        cleaned = cleaned.strip()
        
        # Add semicolon if missing
        if not cleaned.endswith(';'):
            cleaned += ';'
            
        return cleaned
    
    def process_question(self, question: str, user_info: UserInfo) -> None:
        """Process a single question"""
        try:
            print(f"Câu hỏi: {question}")
            
            # Create chain and generate SQL
            chain = self.create_chain(user_info)
            sql_query = chain.invoke({"question": question})
            
            if not sql_query or not sql_query.strip():
                print("Không tạo được truy vấn SQL cho câu hỏi.")
                return
            
            # Clean query
            cleaned_query = self.clean_query(sql_query)
            print(f"SQL được tạo: {cleaned_query}")
            
            # Check permissions with enhanced LLM parsing
            self.permission_manager.check_permissions(
                cleaned_query, user_info.role, self.db_manager
            )
            
            # Execute query
            result = self.db_manager.execute_query(cleaned_query)
            self._display_results(result)
            
        except ValueError as ve:
            print(f"Lỗi quyền truy cập: {ve}")
        except Exception as e:
            print(f"Lỗi khi xử lý câu hỏi: {e}")
    
    def _display_results(self, result: pd.DataFrame) -> None:
        """Display query results"""
        if result.empty:
            print("Không có dữ liệu để hiển thị.")
            return
            
        if 'error' in result.columns:
            print(f"Lỗi: {result.iloc[0, 0]}")
            return
            
        print("\nKết quả:")
        print(result.to_string(index=False))
        print()
    
    def run_interactive_session(self, user_id: str = "4") -> None:
        """Run interactive query session"""
        # Get user information
        user_info = self.db_manager.get_user_info(user_id)
        if not user_info:
            print(f"UserID {user_id} không tồn tại trong hệ thống")
            return
        
        print(f"Đã xác định người dùng: {user_info.role.title()} (ID: {user_info.role_id})")
        print("Đã bật chế độ parsing SQL nâng cao với LLM")
        print("Nhập 'thoát' để kết thúc chương trình\n")
        
        while True:
            try:
                question = input("Nhập câu hỏi của bạn: ").strip()
                if question.lower() in ['thoát', 'exit', 'quit']:
                    print("Đã thoát chương trình.")
                    break
                
                if not question:
                    continue
                
                self.process_question(question, user_info)
                print("-" * 50)
                
            except KeyboardInterrupt:
                print("\nĐã thoát chương trình.")
                break
            except Exception as e:
                print(f"Lỗi không mong muốn: {e}")

def main():
    """Main function"""
    API_KEY = ""
    
    processor = QueryProcessor(API_KEY)
    processor.run_interactive_session()

if __name__ == "__main__":
    main()