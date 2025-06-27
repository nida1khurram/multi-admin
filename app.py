# type: ignore
import streamlit as st
from datetime import datetime, timedelta
import os
import pandas as pd
import numpy as np
from hashlib import md5, sha256
import json
from PIL import Image
import base64
import re

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False
if 'is_admin_owner' not in st.session_state:
    st.session_state.is_admin_owner = False
if 'school_name' not in st.session_state:
    st.session_state.school_name = None
if 'form_key' not in st.session_state:
    st.session_state.form_key = 0
if 'available_months' not in st.session_state:
    st.session_state.available_months = []
if 'current_student_id' not in st.session_state:
    st.session_state.current_student_id = None
if 'last_saved_records' not in st.session_state:
    st.session_state.last_saved_records = None
if 'last_student_name' not in st.session_state:
    st.session_state.last_student_name = ""
if 'last_class_category' not in st.session_state:
    st.session_state.last_class_category = None
if 'last_class_section' not in st.session_state:
    st.session_state.last_class_section = ""
if 'trial_remaining' not in st.session_state:
    st.session_state.trial_remaining = None

# File paths
USER_DB_FILE = "users.json"

def get_admin_files(school_name):
    """Return file paths specific to the school"""
    if not school_name:
        return {
            "fees_csv": None,
            "student_fees_json": None
        }
    safe_school_name = "".join(c for c in school_name.lower() if c.isalnum())
    return {
        "fees_csv": f"fees_data_{safe_school_name}.csv",
        "student_fees_json": f"student_fees_{safe_school_name}.json"
    }

def initialize_files():
    """Initialize all required files"""
    initialize_user_db()
    if st.session_state.authenticated and st.session_state.current_user and st.session_state.is_admin_owner and st.session_state.school_name:
        initialize_school_files()

def initialize_user_db():
    """Initialize the user database if it doesn't exist"""
    if not os.path.exists(USER_DB_FILE):
        with open(USER_DB_FILE, 'w') as f:
            json.dump({}, f)

def initialize_school_files():
    """Initialize school-specific files"""
    if not st.session_state.school_name:
        return  # Skip initialization if no school name is set
    files = get_admin_files(st.session_state.school_name)
    if not files["fees_csv"] or not files["student_fees_json"]:
        return  # Skip if file paths are None
    
    student_fees_file = files["student_fees_json"]
    csv_file = files["fees_csv"]
    
    if not os.path.exists(student_fees_file):
        with open(student_fees_file, 'w') as f:
            json.dump({}, f)
    
    if not os.path.exists(csv_file):
        columns = [
            "ID", "Student Name", "Class Category", "Class Section", "Month",
            "Monthly Fee", "Annual Charges", "Admission Fee",
            "Received Amount", "Payment Method", "Date", "Signature",
            "Entry Timestamp", "Academic Year"
        ]
        pd.DataFrame(columns=columns).to_csv(csv_file, index=False)
    else:
        try:
            df = pd.read_csv(csv_file)
            expected_columns = [
                "ID", "Student Name", "Class Category", "Class Section", "Month",
                "Monthly Fee", "Annual Charges", "Admission Fee",
                "Received Amount", "Payment Method", "Date", "Signature",
                "Entry Timestamp", "Academic Year"
            ]
            for col in expected_columns:
                if col not in df.columns:
                    df[col] = np.nan
            df.to_csv(csv_file, index=False)
        except Exception as e:
            st.error(f"Error initializing CSV: {str(e)}")
            pd.DataFrame(columns=expected_columns).to_csv(csv_file, index=False)


def hash_password(password):
    """Hash a password for storing"""
    return sha256(password.encode('utf-8')).hexdigest()

def verify_password(stored_password, provided_password):
    """Verify a stored password against one provided by user"""
    return stored_password == sha256(provided_password.encode('utf-8')).hexdigest()

def validate_email(email):
    """Validate email format and ensure it's a Gmail address"""
    email_pattern = r'^[a-zA-Z0-9._%+-]+@gmail\.com$'
    return re.match(email_pattern, email) is not None

def authenticate_user(username, password):
    """Authenticate a user and check trial status"""
    try:
        with open(USER_DB_FILE, 'r') as f:
            users = json.load(f)
        
        if username in users:
            if verify_password(users[username]['password'], password):
                st.session_state.authenticated = True
                st.session_state.current_user = username
                st.session_state.is_admin = users[username].get('is_admin', False)
                st.session_state.is_admin_owner = users[username].get('is_admin_owner', False)
                st.session_state.school_name = users[username].get('school_name', None)
                
                # Check trial status
                trial_end = users[username].get('trial_end')
                if trial_end:
                    trial_end_date = datetime.strptime(trial_end, "%Y-%m-%d %H:%M:%S")
                    if datetime.now() > trial_end_date:
                        st.session_state.authenticated = False
                        st.error("Your free trial has expired. Please contact support.")
                        return False
                    remaining = trial_end_date - datetime.now()
                    st.session_state.trial_remaining = remaining
                else:
                    st.session_state.trial_remaining = None
                
                # Initialize school-specific files
                if st.session_state.is_admin:
                    initialize_school_files()
                
                return True
        return False
    except Exception as e:
        st.error(f"Authentication error: {str(e)}")
        return False

def create_user(username, password, email, school_name=None, is_admin=False, is_admin_owner=False):
    """Create a new user account with email, school name, and 1-month trial"""
    try:
        if os.path.exists(USER_DB_FILE):
            with open(USER_DB_FILE, 'r') as f:
                users = json.load(f)
        else:
            users = {}
        
        if not validate_email(email):
            return False, "Please use a valid Gmail address (e.g., username@gmail.com)"
        
        # Check for email uniqueness
        for user in users.values():
            if 'email' in user and user['email'] == email:
                return False, "This Gmail address is already registered. Please use a different Gmail address or log in."
        
        if is_admin_owner and not school_name:
            return False, "School name is required for Admin Owner registration."
        
        trial_start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        trial_end = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        
        users[username] = {
            "password": hash_password(password),
            "is_admin": is_admin,
            "is_admin_owner": is_admin_owner,
            "email": email,
            "school_name": school_name if is_admin_owner else users.get(st.session_state.current_user, {}).get('school_name', None),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "trial_start": trial_start,
            "trial_end": trial_end,
            "created_by": st.session_state.current_user if st.session_state.current_user else "system"
        }
        
        with open(USER_DB_FILE, 'w') as f:
            json.dump(users, f)
        
        if is_admin_owner and school_name:
            st.session_state.school_name = school_name
            initialize_school_files()
        
        return True, "User created successfully"
    except Exception as e:
        return False, f"Error creating user: {str(e)}"
    
def generate_student_id(student_name, class_category):
    """Generate a unique 8-character ID based on student name and class"""
    unique_str = f"{student_name}_{class_category}".encode('utf-8')
    return md5(unique_str).hexdigest()[:8].upper()

def save_to_csv(data):
    """Save data to school-specific CSV with proper validation"""
    try:
        files = get_admin_files(st.session_state.school_name)
        csv_file = files["fees_csv"]
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
        else:
            df = pd.DataFrame(columns=data[0].keys())
        
        new_df = pd.DataFrame(data)
        df = pd.concat([df, new_df], ignore_index=True)
        
        df.to_csv(csv_file, index=False)
        return True
    except Exception as e:
        st.error(f"Error saving data: {str(e)}")
        return False

def load_data():
    """Load data from school-specific CSV with robust error handling"""
    files = get_admin_files(st.session_state.school_name)
    csv_file = files["fees_csv"]
    if not os.path.exists(csv_file):
        return pd.DataFrame()
    
    try:
        try:
            df = pd.read_csv(csv_file)
        except pd.errors.EmptyDataError:
            return pd.DataFrame()
        except pd.errors.ParserError:
            df = pd.read_csv(csv_file, on_bad_lines='skip')
        
        expected_columns = [
            "ID", "Student Name", "Class Category", "Class Section", "Month",
            "Monthly Fee", "Annual Charges", "Admission Fee",
            "Received Amount", "Payment Method", "Date", "Signature",
            "Entry Timestamp", "Academic Year"
        ]
        
        for col in expected_columns:
            if col not in df.columns:
                df[col] = np.nan
        
        try:
            df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%d-%m-%Y')
        except:
            pass
        
        try:
            df['Entry Timestamp'] = pd.to_datetime(df['Entry Timestamp']).dt.strftime('%d-%m-%Y %H:%M')
        except:
            pass
        
        return df.dropna(how='all')
    
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return pd.DataFrame()

def update_data(updated_df):
    """Update the school-specific CSV file with the modified DataFrame"""
    try:
        files = get_admin_files(st.session_state.school_name)
        csv_file = files["fees_csv"]
        updated_df.to_csv(csv_file, index=False)
        return True
    except Exception as e:
        st.error(f"Error updating data: {str(e)}")
        return False

def load_student_fees():
    """Load student-specific fees from JSON file"""
    try:
        files = get_admin_files(st.session_state.school_name)
        student_fees_file = files["student_fees_json"]
        if os.path.exists(student_fees_file):
            with open(student_fees_file, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        st.error(f"Error loading student fees: {str(e)}")
        return {}

def save_student_fees(fees_data):
    """Save student-specific fees to JSON file"""
    try:
        files = get_admin_files(st.session_state.school_name)
        student_fees_file = files["student_fees_json"]
        with open(student_fees_file, 'w') as f:
            json.dump(fees_data, f, indent=4)
        return True
    except Exception as e:
        st.error(f"Error saving student fees: {str(e)}")
        return False

def format_currency(val):
    """Format currency with Pakistani Rupees symbol and thousand separators"""
    try:
        return f"Rs. {int(val):,}" if not pd.isna(val) and val != 0 else "Rs. 0"
    except:
        return "Rs. 0"

def style_row(row):
    """Apply styling to DataFrame rows based on payment status"""
    today = datetime.now()
    is_between_1st_and_10th = 1 <= today.day <= 10
    styles = [''] * len(row)
    
    if is_between_1st_and_10th:
        if row['Monthly Fee'] == 0:
            styles[0] = 'color: red'
        else:
            styles[0] = 'color: green'
    return styles

def get_academic_year(date):
    """Determine academic year based on date"""
    year = date.year
    if date.month >= 4:  # Academic year starts in April
        return f"{year}-{year+1}"
    return f"{year-1}-{year}"

def check_annual_admission_paid(student_id, academic_year):
    """Check if annual charges or admission fee have been paid for the academic year"""
    df = load_data()
    if df.empty:
        return False, False
    
    student_records = df[(df['ID'] == student_id) & (df['Academic Year'] == academic_year)]
    annual_paid = student_records['Annual Charges'].sum() > 0
    admission_paid = student_records['Admission Fee'].sum() > 0
    
    return annual_paid, admission_paid

def get_unpaid_months(student_id):
    """Get list of unpaid months for a specific student"""
    df = load_data()
    all_months = [
        "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER",
        "OCTOBER", "NOVEMBER", "DECEMBER", "JANUARY", "FEBRUARY", "MARCH"
    ]
    
    if df.empty or student_id is None:
        return all_months
    
    paid_months = df[(df['ID'] == student_id) & (df['Monthly Fee'] > 0)]['Month'].unique().tolist()
    
    unpaid_months = [month for month in all_months if month not in paid_months]
    
    return unpaid_months

def update_student_data():
    """Update session state with student data when name or class changes"""
    student_name = st.session_state.get(f"student_name_{st.session_state.form_key}", "")
    class_category = st.session_state.get(f"class_category_{st.session_state.form_key}", None)
    
    if student_name and class_category:
        student_id = generate_student_id(student_name, class_category)
        st.session_state.current_student_id = student_id
        st.session_state.available_months = get_unpaid_months(student_id)
    else:
        st.session_state.current_student_id = None
        st.session_state.available_months = []

def format_trial_remaining(remaining):
    """Format remaining trial time"""
    if remaining is None:
        return "No trial period"
    days = remaining.days
    hours = remaining.seconds // 3600
    minutes = (remaining.seconds % 3600) // 60
    return f"{days} days, {hours} hours, {minutes} minutes"

def home_page():
    """Display beautiful home page with logo and school name at the very top and about section in a dropdown"""
    st.set_page_config(page_title="School Fees Management", layout="wide", page_icon="🏫")
    
    st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stApp {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }
    .title-text {
        font-size: 3.5rem !important;
        font-weight: 600 !important;
        color: #2c3e50 !important;
        text-align: center;
        margin-bottom: 0.5rem !important;
    }
    .subtitle-text {
        font-size: 1.5rem !important;
        font-weight: 400 !important;
        color: #7f8c8d !important;
        text-align: center;
        margin-bottom: 2rem !important;
    }
    .feature-card {
        background-color: white;
        border-radius: 10px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        transition: transform 0.3s ease;
        height: 100%;
    }
    .feature-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 20px rgba(0, 0, 0, 0.1);
    }
    .feature-icon {
        font-size: 2.5rem;
        margin-bottom: 1rem;
        color: #3498db;
    }
    .feature-title {
        font-size: 1.2rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
        color: #2c3e50;
    }
    .feature-desc {
        color: #7f8c8d;
        font-size: 0.9rem;
    }
    .login-btn {
        background: linear-gradient(135deg, #3498db 0%, #2c3e50 100%) !important;
        color: white !important;
        border: none !important;
        padding: 0.5rem 1.5rem;
        border-radius: 8px !important;
        font-weight: 600 !important;
        margin-top: 2rem !important;
    }
    .circle-container {
        display: flex;
        justify-content: center;
        margin-bottom: 1rem;
    }
    .circle {
        width: 200px;
        height: 200px;
        border-radius: 50%;
        background-color: white;
        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
        display: flex;
        justify-content: center;
        align-items: center;
        overflow: hidden;
    }
    .circle img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }
    .expander-content {
        background-color: white;
        border-radius: 10px;
        padding: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .about-heading {
        font-size: 2rem;
        font-weight: 600;
        color: #2c3e50;
        margin-bottom: 1rem;
        text-align: center;
    }
    .about-subheading {
        font-size: 1.5rem;
        font-weight: 500;
        color: #3498db;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
    }
    .about-text {
        color: #7f8c8d;
        font-size: 1rem;
        line-height: 1.6;
    }
    .about-list {
        color: #7f8c8d;
        font-size: 1rem;
        line-height: 1.6;
        margin-left: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Logo at the very top
    st.markdown('<div class="circle-container">', unsafe_allow_html=True)
    
    try:
        with open("school-pic.jpeg", "rb") as img_file:
            img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
        img_html = f'<img src="data:image/jpeg;base64,{img_base64}" alt="School Logo">'
    except:
        img_html = '<div style="color: gray; text-align: center; padding: 20px;">School Logo</div>'
    
    st.markdown(
        f"""
        <div class="circle">
            {img_html}
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Title and Subtitle
    st.markdown('<h1 class="title-text">School Fees Management System</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle-text">Streamline your school\'s fee collection and tracking process with a 1-month free trial!</p>', unsafe_allow_html=True) 
    
    # Feature Cards
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">💰</div>
            <h3 class="feature-title">Fee Collection</h3>
            <p class="feature-desc">Easily record and track student fee payments with a simple, intuitive interface.</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">📊</div>
            <h3 class="feature-title">Reports</h3>
            <p class="feature-desc">Generate detailed reports on fee collection, outstanding payments, and student records.</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">🔒</div>
            <h3 class="feature-title">Secure Access</h3>
            <p class="feature-desc">Role-based authentication ensures only authorized staff can access sensitive data.</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Login Button
    st.markdown('<div style="text-align: center;">', unsafe_allow_html=True)
    if st.button("Sign Up for Free Trial / Login", key="home_login_btn", help="Click to sign up or login"):
        st.session_state.show_login = True
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    
    # About Section in Dropdown
    with st.expander("📌 About This App"):
        st.markdown('<div class="expander-content">', unsafe_allow_html=True)
        st.markdown('<h2 class="about-heading">School Fees Management System - Information, Features & Benefits</h2>', unsafe_allow_html=True)
        
        st.markdown('<h3 class="about-subheading">📌 What is this App?</h3>', unsafe_allow_html=True)
        st.markdown(
            """
            <p class="about-text">
                This is a digital system for schools to easily manage student fee records. It helps track payments, 
                generate reports, and maintain records securely.
            </p>
            """,
            unsafe_allow_html=True
        )
        
        st.markdown('<h3 class="about-subheading">✯ Key Features</h3>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(
                """
                <p class="about-list"><strong>Easy Fee Collection</strong></p>
                <ul class="about-list">
                    <li>Record monthly, annual, and admission fees in one place.</li>
                    <li>Track paid/unpaid students with color-coded status (✅ Paid / ❌ Unpaid).</li>
                </ul>
                <p class="about-list"><strong>Admin Controls</strong></p>
                <ul class="about-list">
                    <li>Set custom fees for each student/class.</li>
                    <li>Manage users (add/remove staff accounts).</li>
                </ul>
                """,
                unsafe_allow_html=True
            )
        with col2:
            st.markdown(
                """
                <p class="about-list"><strong>Student Reports</strong></p>
                <ul class="about-list">
                    <li>View payment history for any student.</li>
                    <li>Check yearly/monthly summaries and download reports.</li>
                </ul>
                <p class="about-list"><strong>Secure & Reliable</strong></p>
                <ul class="about-list">
                    <li>Login with username/password.</li>
                    <li>Data saved securely in files (no risk of losing records).</li>
                </ul>
                <p class="about-list"><strong>Free 1-Month Trial</strong></p>
                <ul class="about-list">
                    <li>New users get 30 days free to test all features.</li> 
                </ul>
                """,
                unsafe_allow_html=True
            )
        
        st.markdown('<h3 class="about-subheading">👍 Why Use This App?</h3>', unsafe_allow_html=True)
        st.markdown(
            """
            <ul class="about-list">
                <li><strong>Saves Time</strong> – No more paper registers or manual calculations.</li>
                <li><strong>Reduces Errors</strong> – Automatic totals and reminders for unpaid fees.</li>
                <li><strong>Always Accessible</strong> – View records anytime, anywhere.</li>
                <li><strong>Data Security</strong> – No more lost fee registers or tampered records.</li>
            </ul>
            """,
            unsafe_allow_html=True
        )
        
        st.markdown('<h3 class="about-subheading">🎯 Perfect For</h3>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(
                """
                <p class="about-list"><strong>School Admins</strong></p>
                <ul class="about-list">
                    <li>Manage all fee records in one place.</li>
                </ul>
                """,
                unsafe_allow_html=True
            )
        with col2:
            st.markdown(
                """
                <p class="about-list"><strong>Accountants</strong></p>
                <ul class="about-list">
                    <li>Generate reports with a single click.</li>
                </ul>
                """,
                unsafe_allow_html=True
            )
        with col3:
            st.markdown(
                """
                <p class="about-list"><strong>Teachers</strong></p>
                <ul class="about-list">
                    <li>Quickly check which students have paid.</li>
                </ul>
                """,
                unsafe_allow_html=True
            )
        
        st.markdown('<h3 class="about-subheading">🚀 Get Started Today!</h3>', unsafe_allow_html=True)
        st.markdown(
            """
            <p class="about-text">
                Try the 1-month free trial – no payment needed!  
            </p>
            """,
            unsafe_allow_html=True
        )
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Footer
    st.markdown("""
    <div style="text-align: center; margin-top: 3rem; color: #7f8c8d; font-size: 0.8rem;">
        <p>© 2025 School Fees Management System | Developed with ❤️ for educational institutions</p>
        <p>Start your 1-month free trial today!</p> 
    </div>
    """, unsafe_allow_html=True)

def login_page():
    """Display login page with signup option and handle authentication"""
    st.title("🔒 School Fees Management - Login / Sign Up")
    
    st.markdown("**New users, including admins, must sign up with their Gmail address to start a 1-month free trial.**") 
    st.markdown("**⚠️ Please use the same Gmail address you used to access this app.**")
    
    tabs = st.tabs(["Sign Up", "Login"])
    
    with tabs[0]:
        with st.form("signup_form"):
            new_username = st.text_input("Username*")
            new_email = st.text_input("Gmail Address*", placeholder="yourname@gmail.com", help="Only the Gmail address used to access this app is allowed.")
            new_password = st.text_input("Password*", type="password", key="signup_pass")
            confirm_password = st.text_input("Confirm Password*", type="password", key="signup_confirm")
            school_name = st.text_input("School Name*", placeholder="Enter your school name", help="Required for admin owners to manage school-specific data.")
            is_admin = st.checkbox("Register as Admin Owner (Manage your school's fees)")
            
            show_password = st.checkbox("Show Password")
            
            if show_password:
                st.text(f"Password will be: {new_password if new_password else '[not set]'}")
            
            signup_submit = st.form_submit_button("Sign Up (Start 1-month Free Trial)") 
            
            if signup_submit:
                if not new_username or not new_password or not new_email or (is_admin and not school_name):
                    st.error("Please fill all required fields (*)")
                elif new_password != confirm_password:
                    st.error("Passwords do not match!")
                else:
                    success, message = create_user(new_username, new_password, new_email, school_name if is_admin else None, is_admin, is_admin)
                    if success:
                        st.session_state.school_name = school_name if is_admin else None
                        st.success(f"{message} Your 1-month free trial has started!") 
                        st.info(f"User '{new_username}' created with email: {new_email}" + (f", School: {school_name}" if is_admin else ""))
                        if authenticate_user(new_username, new_password):
                            st.rerun()
                    else:
                        st.error(message)

    with tabs[1]:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                if authenticate_user(username, password):
                    st.success(f"Welcome {username}!")
                    st.rerun()
                else:
                    st.error("Invalid username or password")

def user_management():
    """Admin interface for user management, showing only users created by the current admin"""
    st.header("👥 User Management")
    
    with st.expander("➕ Create New User"):
        with st.form("create_user_form"):
            new_username = st.text_input("New Username*")
            new_email = st.text_input("Gmail Address*", placeholder="yourname@gmail.com", help="Only Gmail addresses are allowed.")
            new_password = st.text_input("New Password*", type="password", key="new_pass")
            confirm_password = st.text_input("Confirm Password*", type="password", key="confirm_pass")
            is_admin = st.checkbox("Admin User (Sub-Admin)")
            show_password = st.checkbox("Show Password")
            
            if show_password:
                st.text(f"Password will be: {new_password if new_password else '[not set]'}")
            
            submit = st.form_submit_button("Create User")
            
            if submit:
                if not new_username or not new_password or not new_email:
                    st.error("Username, password, and Gmail address are required!")
                elif new_password != confirm_password:
                    st.error("Passwords do not match!")
                else:
                    success, message = create_user(new_username, new_password, new_email, is_admin=is_admin, is_admin_owner=False)
                    if success:
                        st.success(message)
                        st.info(f"User '{new_username}' created with email: {new_email}, Trial: 1-month trial started")
                    else:
                        st.error(message)

    with st.expander("👀 View All Users"):
        try:
            with open(USER_DB_FILE, 'r') as f:
                users = json.load(f)
                
            user_data = []
            for username, details in users.items():
                if details.get('created_by') == st.session_state.current_user or username == st.session_state.current_user:
                    trial_remaining = "N/A"
                    if details.get('trial_end'):
                        trial_end = datetime.strptime(details['trial_end'], "%Y-%m-%d %H:%M:%S")
                        remaining = trial_end - datetime.now()
                        trial_remaining = format_trial_remaining(remaining) if remaining.total_seconds() > 0 else "Expired"
                
                    user_data.append({
                        "Username": username,
                        "Email": details.get('email', 'N/A'),
                        "Role": "Admin Owner" if details.get('is_admin_owner', False) else ("Sub-Admin" if details.get('is_admin', False) else "User"),
                        "School Name": details.get('school_name', 'N/A'),
                        "Created At": details.get('created_at', "Unknown"),
                        "Trial Remaining": trial_remaining,
                        "Created By": details.get('created_by', 'system')
                    })
            
            user_df = pd.DataFrame(user_data)
            if user_df.empty:
                st.info("No users found created by you.")
            else:
                st.dataframe(user_df)
                
                st.subheader("Delete User")
                user_to_delete = st.selectbox(
                    "Select User to Delete",
                    user_df['Username'].tolist(),
                    key="delete_user_select"
                )
                
                if st.button("🗑️ Delete User", key="delete_user_btn"):
                    if user_to_delete == st.session_state.current_user:
                        st.error("You cannot delete your own account!")
                    else:
                        try:
                            with open(USER_DB_FILE, 'r') as f:
                                users = json.load(f)
                            
                            if user_to_delete in users and users[user_to_delete].get('is_admin_owner', False):
                                st.error("Cannot delete Admin Owner account!")
                            elif user_to_delete in users:
                                del users[user_to_delete]
                                
                                with open(USER_DB_FILE, 'w') as f:
                                    json.dump(users, f)
                                
                                st.success(f"User '{user_to_delete}' deleted successfully!")
                                st.rerun()
                            else:
                                st.error("User not found!")
                        except Exception as e:
                            st.error(f"Error deleting user: {str(e)}")

        except Exception as e:
            st.error(f"Error loading users: {str(e)}")

    with st.expander("🔑 Reset Password"):
        try:
            with open(USER_DB_FILE, 'r') as f:
                users = json.load(f)
            
            users_list = [username for username, details in users.items() 
                         if details.get('created_by') == st.session_state.current_user or username == st.session_state.current_user]
            if not users_list:
                st.info("No users found created by you.")
            else:
                selected_user = st.selectbox("Select User", users_list, key="reset_user_select")
                
                with st.form("reset_password_form"):
                    new_password = st.text_input("New Password*", type="password", key="reset_pass")
                    confirm_password = st.text_input("Confirm Password*", type="password", key="reset_confirm")
                    show_password = st.checkbox("Show New Password")
                    
                    if show_password:
                        st.text(f"New password will be: {new_password if new_password else '[not set]'}")
                    
                    reset_btn = st.form_submit_button("Reset Password")
                    
                    if reset_btn:
                        if not new_password:
                            st.error("Password cannot be empty!")
                        elif new_password != confirm_password:
                            st.error("Passwords do not match!")
                        elif users[selected_user].get('is_admin_owner', False) and not st.session_state.is_admin_owner:
                            st.error("Only Admin Owner can reset their own password!")
                        else:
                            users[selected_user]['password'] = hash_password(new_password)
                            with open(USER_DB_FILE, 'w') as f:
                                json.dump(users, f)
                            st.success(f"Password for {selected_user} reset successfully!")
                            st.info(f"New password: {new_password}")
        except Exception as e:
            st.error(f"Error resetting password: {str(e)}")

def set_student_fees():
    """Admin interface to set fees for individual students"""
    st.header("💸 Set Student Fees")
    
    CLASS_CATEGORIES = [
        "Nursery", "KGI", "KGII", 
        "Class 1", "Class 2", "Class 3", "Class 4", "Class 5",
        "Class 6", "Class 7", "Class 8", "Class 9", "Class 10 (Matric)"
    ]
    
    with st.expander("➕ Set Fees for a Student"):
        with st.form("set_fees_form"):
            col1, col2 = st.columns(2)
            with col1:
                student_name = st.text_input("Student Name*", placeholder="Full name")
            with col2:
                class_category = st.selectbox("Class Category*", CLASS_CATEGORIES)
            
            monthly_fee = st.number_input("Monthly Fee*", min_value=0, value=2000, step=100)
            annual_charges = st.number_input("Annual Charges*", min_value=0, value=5000, step=100)
            admission_fee = st.number_input("Admission Fee*", min_value=0, value=1000, step=100)
            
            submit = st.form_submit_button("💾 Save Fee Settings")
            
            if submit:
                if not student_name or not class_category:
                    st.error("Please fill all required fields (*)")
                else:
                    student_id = generate_student_id(student_name, class_category)
                    fees_data = load_student_fees()
                    
                    fees_data[student_id] = {
                        "student_name": student_name,
                        "class_category": class_category,
                        "monthly_fee": monthly_fee,
                        "annual_charges": annual_charges,
                        "admission_fee": admission_fee,
                        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    if save_student_fees(fees_data):
                        st.success(f"Fee settings saved for {student_name} ({class_category})")
                        st.rerun()
                    else:
                        st.error("Failed to save fee settings")

    with st.expander("👀 View All Student Fees"):
        fees_data = load_student_fees()
        if not fees_data:
            st.info("No student fees settings found")
        else:
            fee_records = [
                {
                    "Student ID": student_id,
                    "Student Name": details["student_name"],
                    "Class": details["class_category"],
                    "Monthly Fee": format_currency(details["monthly_fee"]),
                    "Annual Charges": format_currency(details["annual_charges"]),
                    "Admission Fee": format_currency(details["admission_fee"]),
                    "Updated At": details["updated_at"]
                }
                for student_id, details in fees_data.items()
            ]
            fee_df = pd.DataFrame(fee_records)
            st.dataframe(fee_df, use_container_width=True)
            
            st.subheader("Edit/Delete Fee Settings")
            if not fee_df.empty:
                student_to_edit = st.selectbox(
                    "Select Student to Edit/Delete",
                    fee_df["Student ID"].tolist(),
                    format_func=lambda x: f"{fees_data[x]['student_name']} - {fees_data[x]['class_category']}"
                )
                
                with st.form("edit_fees_form"):
                    student_details = fees_data[student_to_edit]
                    col1, col2 = st.columns(2)
                    with col1:
                        edit_name = st.text_input("Student Name*", value=student_details["student_name"])
                    with col2:
                        edit_class = st.selectbox("Class Category*", CLASS_CATEGORIES, 
                                                 index=CLASS_CATEGORIES.index(student_details["class_category"]))
                    
                    edit_monthly_fee = st.number_input("Monthly Fee*", min_value=0, 
                                                      value=int(student_details["monthly_fee"]), step=100)
                    edit_annual_charges = st.number_input("Annual Charges*", min_value=0, 
                                                         value=int(student_details["annual_charges"]), step=100)
                    edit_admission_fee = st.number_input("Admission Fee*", min_value=0, 
                                                        value=int(student_details["admission_fee"]), step=100)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        update_btn = st.form_submit_button("🔄 Update Fees")
                    with col2:
                        delete_btn = st.form_submit_button("🗑️ Delete Fees")
                    
                    if update_btn:
                        if not edit_name or not edit_class:
                            st.error("Please fill all required fields (*)")
                        else:
                            new_student_id = generate_student_id(edit_name, edit_class)
                            fees_data = load_student_fees()
                            
                            if new_student_id != student_to_edit:
                                fees_data.pop(student_to_edit, None)
                            
                            fees_data[new_student_id] = {
                                "student_name": edit_name,
                                "class_category": edit_class,
                                "monthly_fee": edit_monthly_fee,
                                "annual_charges": edit_annual_charges,
                                "admission_fee": edit_admission_fee,
                                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }
                            
                            if save_student_fees(fees_data):
                                st.success(f"Fee settings updated for {edit_name} ({edit_class})")
                                st.rerun()
                            else:
                                st.error("Failed to update fee settings")
                    
                    if delete_btn:
                        fees_data = load_student_fees()
                        if student_to_edit in fees_data:
                            del fees_data[student_to_edit]
                            if save_student_fees(fees_data):
                                st.success("Fee settings deleted successfully")
                                st.rerun()
                            else:
                                st.error("Failed to delete fee settings")

def main_app():
    """Main application after login"""
    st.set_page_config(page_title="School Fees Management", layout="wide")
    st.title(f"📚 {st.session_state.school_name or 'School'} Fees Management System")
    
    # Display trial status in sidebar
    if st.session_state.trial_remaining:
        st.sidebar.markdown(
            f"⏰ Free Trial Remaining: {format_trial_remaining(st.session_state.trial_remaining)}",
            unsafe_allow_html=True
        )
    
    # Display user role and school in sidebar
    role = "Admin Owner" if st.session_state.is_admin_owner else ("Sub-Admin" if st.session_state.is_admin else "User")
    st.sidebar.markdown(f"Logged in as {role}: {st.session_state.current_user}")
    if st.session_state.school_name:
        st.sidebar.markdown(f"School: {st.session_state.school_name}")
    
    if 'menu' not in st.session_state:
        st.session_state.menu = "Enter Fees"
    
    if st.session_state.is_admin:
        menu_options = [
            "Enter Fees", "View All Records", "Paid & Unpaid Students Record", 
            "Student Yearly Report", "User Management", "Set Student Fees"
        ]
        menu = st.sidebar.selectbox("Menu", menu_options, key="menu_select")
        st.session_state.menu = menu
    else:
        menu_options = ["Enter Fees"]
        st.session_state.menu = "Enter Fees"
        menu = "Enter Fees"
    
    if st.sidebar.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.session_state.current_user = None
        st.session_state.is_admin = False
        st.session_state.is_admin_owner = False
        st.session_state.school_name = None
        st.session_state.menu = None
        st.session_state.form_key = 0
        st.session_state.available_months = []
        st.session_state.current_student_id = None
        st.session_state.last_saved_records = None
        st.session_state.last_student_name = ""
        st.session_state.last_class_category = None
        st.session_state.last_class_section = ""
        st.session_state.trial_remaining = None
        st.rerun()
    
    CLASS_CATEGORIES = [
        "Nursery", "KGI", "KGII", 
        "Class 1", "Class 2", "Class 3", "Class 4", "Class 5",
        "Class 6", "Class 7", "Class 8", "Class 9", "Class 10 (Matric)"
    ]
    
    PAYMENT_METHODS = ["Cash", "Bank Transfer", "Cheque", "Online Payment", "Other"]
    
    if menu == "Enter Fees":
        st.header("➕ Enter Fee Details")
        
        with st.form(key=f"fee_form_{st.session_state.form_key}", clear_on_submit=False):
            col1, col2 = st.columns(2)
            with col1:
                student_name = st.text_input(
                    "Student Name*", 
                    placeholder="Full name", 
                    value=st.session_state.last_student_name,
                    key=f"student_name_{st.session_state.form_key}"
                )
            with col2:
                class_category = st.selectbox(
                    "Class Category*", 
                    CLASS_CATEGORIES, 
                    index=CLASS_CATEGORIES.index(st.session_state.last_class_category) if st.session_state.last_class_category in CLASS_CATEGORIES else 0,
                    key=f"class_category_{st.session_state.form_key}"
                )
                class_section = st.text_input(
                    "Class Section", 
                    placeholder="A, B, etc. (if applicable)", 
                    value=st.session_state.last_class_section,
                    key=f"class_section_{st.session_state.form_key}"
                )
            
            update_btn = st.form_submit_button("🔍 Check Student Records")
            
            if update_btn:
                update_student_data()
                st.rerun()
            
            student_id = st.session_state.current_student_id
            
            if student_id:
                st.subheader("📋 Student Payment History")
                df = load_data()
                student_records = df[df['ID'] == student_id]
                
                if not student_records.empty:
                    display_df = student_records[[
                        "Student Name", "Month", "Monthly Fee", "Annual Charges", 
                        "Admission Fee", "Received Amount", "Payment Method", "Date", "Academic Year"
                    ]].sort_values("Date", ascending=False)
                    
                    st.dataframe(
                        display_df.style.format({
                            "Monthly Fee": format_currency,
                            "Annual Charges": format_currency,
                            "Admission Fee": format_currency,
                            "Received Amount": format_currency
                        }),
                        use_container_width=True
                    )
                    
                    total_monthly = student_records["Monthly Fee"].sum()
                    total_annual = student_records["Annual Charges"].sum()
                    total_admission = student_records["Admission Fee"].sum()
                    total_received = student_records["Received Amount"].sum()
                    
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Total Monthly", format_currency(total_monthly))
                    col2.metric("Total Annual", format_currency(total_annual))
                    col3.metric("Total Admission", format_currency(total_admission))
                    col4.metric("Total Received", format_currency(total_received))
                    
                    st.subheader("Payment Status")
                    payment_date = st.session_state.get(f"payment_date_{st.session_state.form_key}", datetime.now())
                    academic_year = get_academic_year(payment_date)
                    
                    annual_paid, admission_paid = check_annual_admission_paid(student_id, academic_year)
                    unpaid_months = st.session_state.available_months
                    
                    col_paid, col_unpaid = st.columns(2)
                    
                    with col_paid:
                        st.markdown("#### ✅ Paid Months")
                        paid_months = student_records[student_records['Monthly Fee'] > 0]['Month'].unique()
                        if len(paid_months) > 0:
                            for month in sorted(paid_months):
                                amount = student_records[student_records['Month'] == month]['Monthly Fee'].iloc[0]
                                st.markdown(f"- {month}: {format_currency(amount)}")
                        else:
                            st.markdown("No months paid yet")
                    
                    with col_unpaid:
                        st.markdown("#### ❌ Unpaid Months")
                        if len(unpaid_months) > 0:
                            for month in unpaid_months:
                                st.markdown(f"- {month}")
                        else:
                            st.markdown("All months paid")
                    
                    st.markdown("---")
                    st.markdown(f"**Annual Fees Paid**: {'✅ Yes' if annual_paid else '❌ No'}")
                    st.markdown(f"**Admission Fee Paid**: {'✅ Yes' if admission_paid else '❌ No'}")
                else:
                    st.info("No fee records found for this student.")
                    unpaid_months = st.session_state.available_months
                    
                    st.markdown("#### ❌ Unpaid Months")
                    if len(unpaid_months) > 0:
                        for month in unpaid_months:
                            st.markdown(f"- {month}")
                    else:
                        st.markdown("All months paid")
            
            payment_date = st.date_input("Payment Date", value=datetime.now(), 
                                       key=f"payment_date_{st.session_state.form_key}")
            academic_year = get_academic_year(payment_date)
            
            fee_type = st.radio("Select Fee Type*", 
                              ["Monthly Fee", "Annual Charges", "Admission Fee"],
                              horizontal=True,
                              key=f"fee_type_{st.session_state.form_key}")
            
            selected_months = []
            monthly_fee = 0
            annual_charges = 0
            admission_fee = 0
            
            fees_data = load_student_fees()
            predefined_fees = fees_data.get(student_id, {})
            default_monthly_fee = predefined_fees.get("monthly_fee", 2000)
            default_annual_charges = predefined_fees.get("annual_charges", 5000)
            default_admission_fee = predefined_fees.get("admission_fee", 1000)
            
            if fee_type == "Monthly Fee":
                if not student_id:
                    st.warning("Please enter Student Name and select Class Category.")
                elif not st.session_state.available_months:
                    st.error("All months have been paid for this student!")
                else:
                    monthly_fee = st.number_input(
                        "Monthly Fee Amount per Month*",
                        min_value=0,
                        value=default_monthly_fee,
                        disabled=bool(predefined_fees) and not st.session_state.is_admin,
                        key=f"monthly_fee_{st.session_state.form_key}"
                    )
                    selected_month = st.selectbox(
                        "Select Month*",
                        ["Select a month"] + st.session_state.available_months,
                        key=f"month_select_{st.session_state.form_key}"
                    )
                    if selected_month != "Select a month":
                        selected_months = [selected_month]
                        st.markdown(f"**Selected Month**: {selected_month}")
                    else:
                        st.markdown("**Selected Month**: None")
            
            elif fee_type == "Annual Charges":
                if student_id:
                    annual_paid, _ = check_annual_admission_paid(student_id, academic_year)
                    if annual_paid:
                        st.error("Annual charges have already been paid for this academic year!")
                    else:
                        selected_months = ["ANNUAL"]
                        annual_charges = st.number_input(
                            "Annual Charges Amount*",
                            min_value=0,
                            value=default_annual_charges,
                            disabled=bool(predefined_fees) and not st.session_state.is_admin,
                            key=f"annual_charges_{st.session_state.form_key}"
                        )
                else:
                    st.warning("Please enter Student Name and select Class Category.")
            
            elif fee_type == "Admission Fee":
                if student_id:
                    _, admission_paid = check_annual_admission_paid(student_id, academic_year)
                    if admission_paid:
                        st.error("Admission fee has already been paid for this academic year!")
                    else:
                        selected_months = ["ADMISSION"]
                        admission_fee = st.number_input(
                            "Admission Fee Amount*",
                            min_value=0,
                            value=default_admission_fee,
                            disabled=bool(predefined_fees) and not st.session_state.is_admin,
                            key=f"admission_fee_{st.session_state.form_key}"
                        )
                else:
                    st.warning("Please enter Student Name and select Class Category.")
            
            col3, col4 = st.columns(2)
            with col3:
                total_amount = (monthly_fee * len(selected_months)) + annual_charges + admission_fee
                st.text_input(
                    "Total Amount",
                    value=format_currency(total_amount),
                    disabled=True,
                    key=f"total_amount_{st.session_state.form_key}"
                )
                
                payment_method = st.selectbox(
                    "Payment Method*",
                    PAYMENT_METHODS,
                    key=f"payment_method_{st.session_state.form_key}"
                )
            with col4:
                received_amount = st.number_input(
                    "Received Amount*",
                    min_value=0,
                    value=total_amount,
                    key=f"received_amount_{st.session_state.form_key}"
                )
                
                signature = st.text_input(
                    "Received By (Signature)*",
                    placeholder="Your name",
                    key=f"signature_{st.session_state.form_key}"
                )
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                submitted = st.form_submit_button("💾 Save Fee Record")
            with col_btn2:
                refresh = st.form_submit_button("🔄 Refresh Form")
            
            if refresh:
                st.session_state.form_key += 1
                st.session_state.last_student_name = ""
                st.session_state.last_class_category = None
                st.session_state.last_class_section = ""
                st.session_state.current_student_id = None
                st.session_state.available_months = []
                st.rerun()
            
            if submitted:
                if not student_name or not class_category or not signature:
                    st.error("Please fill all required fields (*)")
                elif not student_id:
                    st.error("Please enter Student Name and select Class Category.")
                elif fee_type == "Monthly Fee" and not selected_months:
                    st.error("Please select a month for Monthly Fee payment.")
                elif fee_type == "Annual Charges" and annual_paid:
                    st.error("Annual charges have already been paid for this academic year!")
                elif fee_type == "Admission Fee" and admission_paid:
                    st.error("Admission fee has already been paid for this academic year!")
                else:
                    fee_records = []
                    
                    if fee_type in ["Annual Charges", "Admission Fee"]:
                        fee_data = {
                            "ID": student_id,
                            "Student Name": student_name,
                            "Class Category": class_category,
                            "Class Section": class_section,
                            "Month": selected_months[0],
                            "Monthly Fee": 0,
                            "Annual Charges": annual_charges,
                            "Admission Fee": admission_fee,
                            "Received Amount": received_amount,
                            "Payment Method": payment_method,
                            "Date": payment_date.strftime("%Y-%m-%d"),
                            "Signature": signature,
                            "Entry Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "Academic Year": academic_year
                        }
                        fee_records.append(fee_data)
                    
                    elif fee_type == "Monthly Fee":
                        for month in selected_months:
                            fee_data = {
                                "ID": student_id,
                                "Student Name": student_name,
                                "Class Category": class_category,
                                "Class Section": class_section,
                                "Month": month,
                                "Monthly Fee": monthly_fee,
                                "Annual Charges": 0,
                                "Admission Fee": 0,
                                "Received Amount": monthly_fee,
                                "Payment Method": payment_method,
                                "Date": payment_date.strftime("%Y-%m-%d"),
                                "Signature": signature,
                                "Entry Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "Academic Year": academic_year
                            }
                            fee_records.append(fee_data)
                    
                    if save_to_csv(fee_records):
                        st.session_state.last_student_name = student_name
                        st.session_state.last_class_category = class_category
                        st.session_state.last_class_section = class_section or ""
                        
                        st.session_state.form_key += 1
                        st.session_state.available_months = get_unpaid_months(student_id)
                        st.session_state.last_saved_records = fee_records
                        st.success("✅ Fee record(s) saved successfully!")
                        st.balloons()
                        st.rerun()
            
            if st.session_state.last_saved_records:
                st.subheader("📋 Last Saved Fee Record(s)")
                saved_df = pd.DataFrame(st.session_state.last_saved_records)
                display_df = saved_df[[
                    "Student Name", "Class Category", "Month", "Monthly Fee", 
                    "Annual Charges", "Admission Fee", "Received Amount", 
                    "Payment Method", "Date", "Signature"
                ]]
                st.dataframe(
                    display_df.style.format({
                        "Monthly Fee": format_currency,
                        "Annual Charges": format_currency,
                        "Admission Fee": format_currency,
                        "Received Amount": format_currency
                    }),
                    use_container_width=True
                )
    
    elif menu == "Set Student Fees":
        if not st.session_state.is_admin:
            st.error("🚫 Access Denied: You do not have permission to view this page.")
            st.session_state.menu = "Enter Fees"
            st.rerun()
        else:
            set_student_fees()
    
    elif menu in ["View All Records", "Paid & Unpaid Students Record", "Student Yearly Report", "User Management"]:
        if not st.session_state.is_admin:
            st.error("🚫 Access Denied: You do not have permission to view this page.")
            st.session_state.menu = "Enter Fees"
            st.rerun()
        else:
            if menu == "View All Records":
                st.header("👀 View All Fee Records")
                
                df = load_data()
                if df.empty:
                    st.info("No fee records found")
                else:
                    tabs = st.tabs(["All Records"] + CLASS_CATEGORIES)
                    
                    with tabs[0]:
                        st.subheader("All Fee Records")
                        
                        with st.expander("📝 Edit/Delete Records", expanded=False):
                            st.markdown("## Select a record to edit or delete:")
                            
                            edit_index = st.selectbox(
                                "Select Record",
                                options=df.index,
                                format_func=lambda x: f"{df.loc[x, 'Student Name']} - {df.loc[x, 'Class Category']} - {df.loc[x, 'Month']}"
                            )
                            
                            with st.form("edit_form"):
                                record = df.loc[edit_index]
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    edit_name = st.text_input("Student Name", value=record['Student Name'])
                                    edit_class = st.selectbox("Class Category", CLASS_CATEGORIES, 
                                                            index=CLASS_CATEGORIES.index(record['Class Category']))
                                    edit_section = st.text_input("Class Section", value=record['Class Section'])
                                    edit_month = st.selectbox("Month", [
                                        "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER",
                                        "OCTOBER", "NOVEMBER", "DECEMBER", "JANUARY", "FEBRUARY", "MARCH",
                                        "ANNUAL", "ADMISSION"
                                    ], index=[
                                        "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER",
                                        "OCTOBER", "NOVEMBER", "DECEMBER", "JANUARY", "FEBRUARY", "MARCH",
                                        "ANNUAL", "ADMISSION"
                                    ].index(record['Month']))
                                with col2:
                                    edit_monthly_fee = st.number_input("Monthly Fee", value=float(record['Monthly Fee'] or 0))
                                    edit_annual_charges = st.number_input("Annual Charges", value=float(record['Annual Charges'] or 0))
                                    edit_admission_fee = st.number_input("Admission Fee", value=float(record['Admission Fee'] or 0))
                                    edit_received = st.number_input("Received Amount", value=float(record['Received Amount'] or 0))
                                    edit_payment_method = st.selectbox("Payment Method", PAYMENT_METHODS, 
                                                                     index=PAYMENT_METHODS.index(record['Payment Method'] if pd.notna(record['Payment Method']) else "Cash"))
                                
                                try:
                                    edit_date_value = datetime.strptime(record['Date'], '%d-%m-%Y')
                                except:
                                    try:
                                        edit_date_value = datetime.strptime(record['Date'], '%Y-%m-%d')
                                    except:
                                        edit_date_value = datetime.now()
                                
                                edit_date = st.date_input("Payment Date", value=edit_date_value)
                                edit_signature = st.text_input("Received By (Signature)", value=record['Signature'])
                                edit_academic_year = st.text_input("Academic Year", 
                                                                 value=record['Academic Year'] if pd.notna(record['Academic Year']) else get_academic_year(edit_date))
                                
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    update_btn = st.form_submit_button("🔄 Update Record")
                                with col2:
                                    delete_btn = st.form_submit_button("🗑️ Delete Record")
                                
                                if update_btn:
                                    df.loc[edit_index, 'Student Name'] = edit_name
                                    df.loc[edit_index, 'Class Category'] = edit_class
                                    df.loc[edit_index, 'Class Section'] = edit_section
                                    df.loc[edit_index, 'Month'] = edit_month
                                    df.loc[edit_index, 'Monthly Fee'] = edit_monthly_fee
                                    df.loc[edit_index, 'Annual Charges'] = edit_annual_charges
                                    df.loc[edit_index, 'Admission Fee'] = edit_admission_fee
                                    df.loc[edit_index, 'Received Amount'] = edit_received
                                    df.loc[edit_index, 'Payment Method'] = edit_payment_method
                                    df.loc[edit_index, 'Date'] = edit_date.strftime('%d-%m-%Y')
                                    df.loc[edit_index, 'Signature'] = edit_signature
                                    df.loc[edit_index, 'Academic Year'] = edit_academic_year
                                    df.loc[edit_index, 'Entry Timestamp'] = datetime.now().strftime('%d-%m-%Y %H:%M')
                                    
                                    if update_data(df):
                                        st.success("✅ Record updated successfully!")
                                        st.rerun()
                                
                                if delete_btn:
                                    df = df.drop(index=edit_index)
                                    if update_data(df):
                                        st.success("✅ Record deleted successfully!")
                                        st.rerun()
                        
                        st.dataframe(
                            df.style.apply(style_row, axis=1).format({
                                'Monthly Fee': format_currency,
                                'Annual Charges': format_currency,
                                'Admission Fee': format_currency,
                                'Received Amount': format_currency
                            }),
                            use_container_width=True
                        )
                    
                    for i, category in enumerate(CLASS_CATEGORIES, start=1):
                        with tabs[i]:
                            st.subheader(f"{category} Records")
                            class_df = df[df['Class Category'] == category]
                            
                            if not class_df.empty:
                                st.dataframe(
                                    class_df.style.apply(style_row, axis=1).format({
                                        'Monthly Fee': format_currency,
                                        'Annual Charges': format_currency,
                                        'Admission Fee': format_currency,
                                        'Received Amount': format_currency
                                    }),
                                    use_container_width=True
                                )
                                
                                st.subheader("Summary")
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("Total Students", class_df['Student Name'].nunique())
                                with col2:
                                    st.metric("Total Received", format_currency(class_df['Received Amount'].sum()))
                                with col3:
                                    unpaid = class_df[class_df['Monthly Fee'] == 0]['Student Name'].nunique()
                                    st.metric("Unpaid Students", unpaid, delta_color="inverse")
                                
                                st.markdown("Monthly Collection:")
                                monthly_summary = class_df.groupby('Month')['Received Amount'].sum().reset_index()
                                st.bar_chart(monthly_summary.set_index('Month'))
                    
                    st.divider()
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download All Records as CSV",
                        data=csv,
                        file_name=f"fee_records_{st.session_state.school_name or st.session_state.current_user}.csv",
                        mime="text/csv"
                    )
            
            elif menu == "Paid & Unpaid Students Record":
                st.header("✅ Paid & ❌ Unpaid Students Record")
                df = load_data()
                
                if df.empty:
                    st.info("No fee records found")
                else:
                    all_students = df[['ID', 'Student Name', 'Class Category']].drop_duplicates()
                    
                    MONTHS = [
                        "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER",
                        "OCTOBER", "NOVEMBER", "DECEMBER", "JANUARY", "FEBRUARY", "MARCH"
                    ]
                    
                    all_combinations = pd.DataFrame([
                        (student['ID'], student['Student Name'], student['Class Category'], month)
                        for _, student in all_students.iterrows()
                        for month in MONTHS
                    ], columns=['ID', "Student Name", "Class Category", "Month"])
                    
                    payment_records = df[["ID", "Month", "Monthly Fee", "Received Amount"]]
                    merged = pd.merge(all_combinations, payment_records, on=["ID", "Month"], how="left")
                    
                    fees_data = load_student_fees()
                    
                    def get_student_fee(student_id):
                        if student_id in fees_data:
                            return fees_data[student_id]["monthly_fee"]
                        student_payments = df[(df['ID'] == student_id) & (df['Monthly Fee'] > 0)]
                        if not student_payments.empty:
                            return student_payments['Monthly Fee'].iloc[-1]
                        return 2000
                        
                    merged['Estimated Monthly Fee'] = merged['ID'].apply(get_student_fee)
                        
                    merged['Status'] = merged['Monthly Fee'].apply(
                        lambda x: "Paid" if pd.notna(x) and x > 0 else "Unpaid"
                    )
                    merged['Outstanding'] = merged.apply(
                        lambda row: 0 if row['Status'] == "Paid" else row['Estimated Monthly Fee'],
                        axis=1
                    )
                        
                    tabs = st.tabs(MONTHS)
                        
                    for i, month in enumerate(MONTHS):
                        with tabs[i]:
                            month_data = merged[merged['Month'] == month].copy()
                                
                            if not month_data.empty:
                                total_students = len(month_data)
                                paid_students = len(month_data[month_data["Status"] == "Paid"])
                                unpaid_students = total_students - paid_students
                                total_outstanding = month_data[month_data["Status"] == "Unpaid"]["Outstanding"].sum()
                                    
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("Total Students", total_students)
                                with col2:
                                    st.metric("Paid Students", paid_students)
                                with col3:
                                    st.metric("Unpaid Students", unpaid_students, 
                                            delta=f"Rs. {int(total_outstanding):,}" if total_outstanding > 0 else "Rs. 0")
                                    
                                def color_status(val):
                                    color = "green" if val == "Paid" else "red"
                                    return f"color: {color}"
                                    
                                display_df = month_data[[
                                    "Student Name", "Class Category", "Estimated Monthly Fee", 
                                    "Received Amount", "Outstanding", "Status"
                                ]]
                                display_df = display_df.rename(columns={
                                    "Estimated Monthly Fee": "Monthly Fee",
                                    "Received Amount": "Amount Paid",
                                    "Outstanding": "Balance Due"
                                })
                                    
                                st.dataframe(
                                    display_df.style.format({
                                        "Monthly Fee": format_currency,
                                        "Amount Paid": format_currency,
                                        "Balance Due": format_currency
                                    }).applymap(color_status, subset=["Status"]),
                                    use_container_width=True
                                )
                                        
                                csv = display_df.to_csv(index=False).encode("utf-8")
                                st.download_button(
                                    label=f"📥 Download {month} Data",
                                    data=csv,
                                    file_name=f"{month.lower()}_payment_status_{st.session_state.school_name or st.session_state.current_user}.csv",
                                    mime="text/csv",
                                    key=f"download_month_{month.lower()}"
                                )
                            
                            st.subheader("Overall Payment Status")
                            student_summary = merged.groupby(["ID", "Student Name", "Class Category"]).agg({
                                "Status": lambda x: (x == "Unpaid").sum(),
                                "Outstanding": "sum"
                            }).reset_index()
                            student_summary.columns = [
                                "ID", "Student Name", "Class Category", "Unpaid Months", "Total Outstanding"
                            ]
                    
                            st.dataframe(
                                student_summary.style.format({
                                    "Total Outstanding": format_currency
                                }),
                                use_container_width=True
                            )
                                    
                            csv = student_summary.to_csv(index=False).encode("utf-8")
                            st.download_button(
                                label="📥 Download All Records as CSV",
                                data=csv,
                                file_name=f"all_fee_records_{st.session_state.school_name or st.session_state.current_user}.csv",
                                mime="text/csv",
                                key="download_all_records"
                            )
            
            elif menu == "Student Yearly Report":
                st.header("📊 Student Yearly Fee Report")
                
                df = load_data()
                if df.empty:
                    st.info("No fee records found")
                else:
                    all_classes = sorted(df["Class Category"].unique())
                    selected_class = st.selectbox("Select Class", all_classes, key="class_selector")
                    
                    class_students = sorted(df[df["Class Category"] == selected_class]["Student Name"].unique())
                    
                    if not class_students:
                        st.warning(f"No students found in {selected_class}")
                    else:
                        selected_student = st.selectbox("Select Student", class_students, key="student_selector")
                        
                        student_data = df[(df["Student Name"] == selected_student) & 
                                        (df["Class Category"] == selected_class)]
                        
                        if student_data.empty:
                            st.warning(f"No records found for {selected_student} in {selected_class}")
                        else:
                            st.subheader(f"Yearly Report for {selected_student}")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown(f"**Class**: {selected_class}")
                            with col2:
                                section = student_data.iloc[0]["Class Section"] if "Class Section" in student_data.columns else "N/A"
                                st.markdown(f"**Section**: {section if pd.notna(section) else 'N/A'}")
                            
                            st.subheader("Fee Summary")
                            
                            total_monthly_fee = student_data["Monthly Fee"].sum()
                            annual_charges = student_data["Annual Charges"].sum()
                            admission_fee = student_data["Admission Fee"].sum()
                            total_received = student_data["Received Amount"].sum()
                            
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Total Monthly Fee", format_currency(total_monthly_fee))
                            with col2:
                                st.metric("Annual Charges", format_currency(annual_charges))
                            with col3:
                                st.metric("Admission Fee", format_currency(admission_fee))
                            with col4:
                                st.metric("Total Received", format_currency(total_received))
                            
                            st.subheader("Monthly Fee Details")
                            
                            all_months = [
                                "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER",
                                "OCTOBER", "NOVEMBER", "DECEMBER", "JANUARY", "FEBRUARY", "MARCH"
                            ]
                            
                            monthly_report = pd.DataFrame({"Month": all_months})
                            monthly_data = student_data.groupby("Month").agg({
                                "Monthly Fee": "sum",
                                "Received Amount": "sum"
                            }).reset_index()
                            
                            monthly_report = monthly_report.merge(monthly_data, on="Month", how="left").fillna(0)
                            monthly_report["Status"] = monthly_report.apply(
                                lambda row: "Paid" if row["Monthly Fee"] > 0 else "Unpaid",
                                axis=1
                            )
                            
                            def color_unpaid(val):
                                if val == "Unpaid":
                                    return "color: red"
                                return ""
                            
                            st.dataframe(
                                monthly_report.style
                                .applymap(color_unpaid, subset=["Status"])
                                .format({
                                    "Monthly Fee": format_currency,
                                    "Received Amount": format_currency
                                }),
                                use_container_width=True
                            )
                            
                            st.subheader("Payment Trends")
                            st.line_chart(monthly_report.set_index("Month")[["Monthly Fee", "Received Amount"]])
                            
                            st.divider()
                            csv = monthly_report.to_csv(index=False).encode("utf-8")
                            st.download_button(
                                label="📥 Download Student Report",
                                data=csv,
                                file_name=f"{selected_student}_fee_report_{st.session_state.school_name or st.session_state.current_user}.csv",
                                mime="text/csv"
                            )
            
            elif menu == "User Management":
                user_management()

def main():
    initialize_files()
    
    if 'show_login' not in st.session_state:
        st.session_state.show_login = False
    
    if not st.session_state.authenticated:
        if st.session_state.show_login:
            login_page()
        else:
            home_page()
    else:
        main_app()

if __name__ == "__main__":
    main()