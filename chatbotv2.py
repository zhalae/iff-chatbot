import streamlit as st
import pandas as pd
import json
from datetime import datetime, date
import plotly.express as px
from openai import OpenAI

# Set page config
st.set_page_config(page_title="Continuum by IFF", layout="wide")

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_page' not in st.session_state:
    st.session_state.current_page = "Instructions"

# Load JSON data
@st.cache_data
def load_data():
    with open('csvjson (4).json', 'r') as f:
        time_off_data = json.load(f)
    with open('workdays.json', 'r') as f:
        workdays_data = json.load(f)
    with open('projectLog.json', 'r') as f:
        project_log_data = json.load(f)
    
    df_project_log = pd.DataFrame(project_log_data)
    df_project_log['Date'] = pd.to_datetime(df_project_log['Date'], format='%m/%d/%Y')
    df_time_off = pd.DataFrame(time_off_data)
    df_workdays = pd.DataFrame(workdays_data)
    
    df_merged = df_workdays.merge(df_time_off, on='Employee')
    df_merged = df_merged.merge(df_project_log.groupby('Employee')['Hours Worked'].sum().reset_index(), on='Employee')
    
    return df_merged, df_project_log, df_time_off, df_workdays

df_merged, df_project_log, df_time_off, df_workdays = load_data()

# Function to get employee data
def get_employee_data(employee_name, start_date=None, end_date=None):
    if start_date is None:
        start_date = df_project_log['Date'].min()
    if end_date is None:
        end_date = df_project_log['Date'].max()
    
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)
    
    employee_data = df_project_log[(df_project_log['Employee'] == employee_name) & 
                                   (df_project_log['Date'] >= start_date) & 
                                   (df_project_log['Date'] <= end_date)]
    
    total_hours = employee_data['Hours Worked'].sum()
    projects = employee_data['Project'].unique().tolist()
    coworkers = df_project_log[(df_project_log['Project'].isin(projects)) & 
                               (df_project_log['Employee'] != employee_name)]['Employee'].unique().tolist()
    
    time_off = df_time_off[df_time_off['Employee'] == employee_name]['Time Off Days'].values[0] if not df_time_off[df_time_off['Employee'] == employee_name].empty else 'N/A'
    workdays = df_workdays[df_workdays['Employee'] == employee_name]['Workdays'].values[0] if not df_workdays[df_workdays['Employee'] == employee_name].empty else 'N/A'
    
    return {
        'total_hours': total_hours,
        'projects': projects,
        'coworkers': coworkers,
        'time_off': time_off,
        'workdays': workdays
    }

# Login function
def login(username, password):
    if username == "Zhalae" and password == "password":
        st.session_state.logged_in = True
        return True
    return False

# Logout function
def logout():
    st.session_state.logged_in = False

# Function to filter data
def filter_data(df, project, employee, month):
    filtered_df = df.copy()
    if project != "All":
        filtered_df = filtered_df[filtered_df['Employee'].isin(df_project_log[df_project_log['Project'] == project]['Employee'])]
    if employee != "All":
        filtered_df = filtered_df[filtered_df['Employee'] == employee]
    if month != "All":
        month_number = datetime.strptime(month, "%B").month
        filtered_df = filtered_df[filtered_df['Employee'].isin(df_project_log[df_project_log['Date'].dt.month == month_number]['Employee'])]
    return filtered_df

# Login page
def login_page():
    st.title("Login to Continuum by IFF")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if login(username, password):
            st.success("Logged in successfully!")
            st.rerun()
        else:
            st.error("Invalid username or password")

# Main app
def main_app():
    # Logout button
    col1, col2, col3 = st.columns([1,1,1])
    with col3:
        if st.button("Logout"):
            logout()
            st.rerun()

    st.title("Continuum by IFF")

    # Sidebar for chatbot
    with st.sidebar:
        st.title("IFF Continuum ChatBot")
        
        try:
            client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
        except Exception as e:
            st.error(f"Error initializing OpenAI client: {str(e)}")
            return
        # Get unique employee names
        employee_names = sorted(df_merged['Employee'].unique())

        # # Create a text input for searching employees
        # search_term = st.text_input("Search for an employee:")

        # Filter employee names based on search term
        filtered_employees = [name for name in employee_names]

        # Create a selectbox with filtered employee names
        employee_name = st.selectbox("Select or type employee name:", 
                                    options=filtered_employees)

        # Optional date inputs
        use_date_range = st.checkbox("Use date range")
        if use_date_range:
            start_date = st.date_input("Start date:", datetime(2023, 1, 1))
            end_date = st.date_input("End date:", datetime(2023, 12, 31))
        else:
            start_date = None
            end_date = None

        # Larger question input box
        user_input = st.text_area("Ask me a question about " + employee_name + ", or if you need any other assistance!", height=150)

        if st.button("Generate"):
            if employee_name and user_input:
                try:
                    employee_data = get_employee_data(employee_name, start_date, end_date)
                    
                    context = f"""
                    Employee: {employee_name}
                    {"Date Range: " + str(start_date) + " to " + str(end_date) if use_date_range else ""}
                    Total Hours Worked: {employee_data['total_hours']}
                    Projects Worked On: {', '.join(employee_data['projects'])}
                    Coworkers: {', '.join(employee_data['coworkers'])}
                    Total Time Off Days: {employee_data['time_off']}
                    Total Workdays: {employee_data['workdays']}
                    """

                    completion = client.chat.completions.create(
                        model="ggml-model-Q4_K_M.gguf",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant for IFF Continuum. Answer questions based on the provided employee information or navigate to pages. Be concise and don't ask follow-up questions."},
                            {"role": "user", "content": f"Context: {context}\n\nQuestion or Navigation: {user_input}"}
                        ],
                        temperature=0.7,
                    )
                    response = completion.choices[0].message.content
                    st.write("Response:", response)
                    
                    # Check for navigation commands in the response
                    navigation_keywords = {"home": "Home", "instructions": "Instructions", "attendance": "Attendance", 
                                        "my attendance": "My Attendance", "report": "Attendance Report", 
                                        "visualization": "Visualization"}
                    for keyword, page in navigation_keywords.items():
                        if keyword in response.lower():
                            st.session_state.current_page = page
                            st.rerun()
                except Exception as e:
                    st.error(f"Error generating response: {str(e)}")
            else:
                st.error("Please select an employee and enter a question.")

    # Main content
    st.header("ATTENDANCE")

    # Navigation
    pages = ["Instructions", "Attendance", "My Attendance", "Attendance Report", "Visualization"]
    st.session_state.current_page = st.selectbox("Navigate to", pages, index=pages.index(st.session_state.current_page))

    if st.session_state.current_page == "Instructions":
        st.write("This is a mock version of 'Continuum by IFF'. Use the chatbot to help navigate the site or find information about employee attendance data.")

    elif st.session_state.current_page == "Attendance":
        st.write("This is the attendance page")

    elif st.session_state.current_page == "My Attendance":
        st.subheader("My Attendance")
        st.write("Name: Zhalae Daneshvari")
        st.write("Job Title: Innovative Technology Consultant")
        
        if 'zhalae_data' not in st.session_state:
            st.session_state.zhalae_data = pd.DataFrame({
                'Date': pd.date_range(start='2023-01-01', end='2023-12-31', freq='D'),
                'Hours Worked': [8 if i.weekday() < 5 else 0 for i in pd.date_range(start='2023-01-01', end='2023-12-31', freq='D')],
                'Time Off': [0] * 365
            })

        st.subheader("Log Attendance")
        col1, col2, col3 = st.columns(3)
        with col1:
            log_date = st.date_input("Date", date.today())
        with col2:
            hours_worked = st.number_input("Hours Worked", min_value=0, max_value=24, value=8)
        with col3:
            time_off = st.number_input("Time Off (hours)", min_value=0, max_value=24, value=0)

        if st.button("Log Attendance"):
            idx = st.session_state.zhalae_data.index[st.session_state.zhalae_data['Date'] == pd.Timestamp(log_date)].tolist()[0]
            st.session_state.zhalae_data.at[idx, 'Hours Worked'] = hours_worked
            st.session_state.zhalae_data.at[idx, 'Time Off'] = time_off
            st.success(f"Attendance logged for {log_date}")

        monthly_summary = st.session_state.zhalae_data.resample('M', on='Date').sum().reset_index()
        monthly_summary['Month'] = monthly_summary['Date'].dt.strftime('%b')
        monthly_summary['Workdays'] = monthly_summary['Hours Worked'].apply(lambda x: round(x/8))
        
        st.subheader("Monthly Summary")
        st.dataframe(monthly_summary[['Month', 'Hours Worked', 'Workdays', 'Time Off']])
        
        fig1 = px.bar(monthly_summary, x='Month', y='Hours Worked', title='Hours Worked by Month')
        st.plotly_chart(fig1)

        fig2 = px.bar(monthly_summary, x='Month', y=['Workdays', 'Time Off'], 
                      title='Workdays and Time Off Days by Month', barmode='group')
        st.plotly_chart(fig2)

    elif st.session_state.current_page == "Attendance Report":
        st.subheader("Attendance Report")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            project = st.selectbox("Select Project", ["All"] + df_project_log['Project'].unique().tolist(), key='report_project')
        with col2:
            employee = st.selectbox("Select Employees", ["All"] + df_merged['Employee'].tolist(), key='report_employee')
        with col3:
            month = st.selectbox("Select Month", ["All", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], key='report_month')

        filtered_df = filter_data(df_merged, project, employee, month)
        st.dataframe(filtered_df)

    elif st.session_state.current_page == "Visualization":
        st.subheader("Visualization")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            project = st.selectbox("Select Project", ["All"] + df_project_log['Project'].unique().tolist(), key='viz_project')
        with col2:
            employee = st.selectbox("Select Employees", ["All"] + df_merged['Employee'].tolist(), key='viz_employee')
        with col3:
            month = st.selectbox("Select Month", ["All", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], key='viz_month')

        filtered_df = filter_data(df_merged, project, employee, month)
        
        fig1 = px.bar(filtered_df, x='Employee', y='Hours Worked', title='Hours Worked by Employee')
        st.plotly_chart(fig1)

        fig2 = px.bar(filtered_df, x='Employee', y=['Workdays', 'Time Off Days'], 
                      title='Workdays and Time Off Days by Employee', barmode='group')
        st.plotly_chart(fig2)

# Main execution
if not st.session_state.logged_in:
    login_page()
else:
    main_app()