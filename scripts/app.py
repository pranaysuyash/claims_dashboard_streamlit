import matplotlib
matplotlib.use('Agg')

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
from scipy.stats import ttest_ind
import os
from fuzzywuzzy import process

# Change the working directory to the script's directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

class DiseaseCategorizer:
    def __init__(self, category_file, tests_file):
        self.category_df = pd.read_csv(category_file)
        self.disease_to_category = dict(zip(self.category_df['disease'], self.category_df['Disease Category']))

         # Load the tests data
        script_dir = os.path.dirname(os.path.abspath(__file__))
        tests_path = os.path.join(script_dir, '..', 'data', tests_file)
        self.tests_df = pd.read_csv(tests_path)
        self.category_to_tests = dict(zip(self.tests_df['Disease Category'], self.tests_df['Associated Tests']))

    def categorize(self, disease):
        if pd.isna(disease) or not isinstance(disease, str):
            return "Uncategorized"
        
        if disease in self.disease_to_category:
            return self.disease_to_category[disease]
        
        closest_match = process.extractOne(disease, self.disease_to_category.keys())
        if closest_match and closest_match[1] >= 80:
            return self.disease_to_category[closest_match[0]]
        
        return "Other"
    
    def get_tests(self, category):
        return self.category_to_tests.get(category, "No tests specified")


categorizer = DiseaseCategorizer('../data/disease_categories.csv', 'disease_test.csv')

app = Flask(__name__, static_folder='../static', template_folder='../templates')
CORS(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}),400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}),400
    try:
        df = pd.read_csv(file)
    except Exception as e:
        return jsonify({'error': 'Error reading file: {str(e)}'}), 500
    results = process_data(df)
    return jsonify(results)

@app.route('/update_disease_chart', methods=['POST'])
def update_disease_chart():
    data = request.json['data']
    df = pd.DataFrame(data)
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.barplot(x='Count', y='Category', data=df, ax=ax)
    ax.set_title('Distribution of Disease Categories')
    ax.set_xlabel('Number of Claims')
    ax.set_ylabel('Disease Category')
    img = io.BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    return jsonify(base64.b64encode(img.getvalue()).decode())

def process_data(df):
    results = {
        'charts': {},
        'tables': {},
        'statistics': {},
        'data': {}
    }

    df_copy = df.copy()
    df_copy.drop(columns=["hospital_address", "pincode"], axis=1, inplace=True)

    df_copy["admission_date"] = pd.to_datetime(df['admission_date'], format='%d/%m/%Y', errors='coerce')
    df_copy["discharge_date"] = pd.to_datetime(df['discharge_date'], format='%d/%m/%Y', errors='coerce')
    df_copy["stay_duration"] = df_copy["discharge_date"] - df_copy["admission_date"]
    df_copy["dob"] = pd.to_datetime(df['dob'], format='%d/%m/%Y', errors='coerce')
    df_copy["age_at_admission"] = ((df_copy["admission_date"] - df_copy["dob"]).dt.days / 365.25).round(2)
    df_copy["amount_paid"] = pd.to_numeric(df_copy["amount_paid"], errors='coerce').fillna(0)
    df_copy["created_date"] = pd.to_datetime(df['created_date'], format='%m/%d/%y %H:%M', errors='coerce')

    # Ensure 'disease' column contains strings
    df_copy['disease'] = df_copy['disease'].astype(str)

    # Apply disease categorization
    df_copy['disease_category'] = df_copy['disease'].apply(categorizer.categorize)
    df_non_zero = df_copy[df_copy['claim_amount'] > 0]

    # Generate disease tests table
    disease_tests_table = display_disease_tests_table(df_copy, categorizer)
    results['tables']['disease_tests'] = disease_tests_table

    results['charts']['age_distribution'] = plot_age_distribution(df_copy)
    results['charts']['amount_paid_vs_age'] = plot_amount_paid_vs_age(df_copy)
    results['charts']['monthly_claims_trend'] = plot_monthly_claims_trend(df_copy)
    results['charts']['daily_claims'] = plot_daily_claims(df_copy)
    results['charts']['weekly_claim_creation'] = plot_weekly_claim_creation(df_copy)
    results['charts']['weekly_admission'] = plot_weekly_admission(df_copy)
    results['charts']['weekly_discharge'] = plot_weekly_discharge(df_copy)
    results['charts']['monthly_claim_creation'] = plot_monthly_claim_creation(df_copy)
    results['charts']['monthly_admission'] = plot_monthly_admission(df_copy)
    results['charts']['monthly_discharge'] = plot_monthly_discharge(df_copy)
    results['charts']['disease_category_distribution'], results['data']['disease_category_counts'] = plot_disease_category_distribution(df_copy)

    # Pivot table for claims
    pivot_df = pd.pivot_table(df_non_zero, values='claim_amount', index='hospital_name', 
                          columns='disease_category', aggfunc='sum', fill_value=0)
    
    pivot_df['Total'] = pivot_df.sum(axis=1)
    pivot_df = pivot_df.reset_index()  # Reset index to make 'hospital_name' a column

    # pivot_html = pivot_df.to_html(classes='display', table_id='pivot_claims', index=False)
    pivot_html = pivot_df.to_html(classes='display', table_id='pivot_claims', index=False)
    results['tables']['pivot_claims'] = pivot_html
    # Create a hierarchical structure
    hierarchy = {}
    for _, row in pivot_df.iterrows():
        hospital = row['hospital_name']
        hierarchy[hospital] = row.drop(['hospital_name', 'Total']).to_dict()
        
    # Log the hierarchy data before sending it to the frontend
    print("Hierarchy Data:", hierarchy)
    print("Column Names:", list(pivot_df.columns))

    disease_freq = df_copy.groupby(['disease', 'disease_category']).size().reset_index(name='count')
    disease_freq = disease_freq.sort_values('count', ascending=False)
    
    category_counts = df_copy['disease_category'].value_counts().reset_index()
    category_counts.columns = ['Category', 'Count']
    category_counts = category_counts.sort_values('Count', ascending=False)
    
    # Generate tables with advanced features
    results['tables']['descriptive_stats'] = generate_table(df_copy.describe(include=['number']).reset_index(), 'descriptive_stats')
    results['tables']['disease_freq'] = generate_table(disease_freq, 'disease_freq')
    results['tables']['hospital_freq'] = generate_table(df_copy['hospital_name'].value_counts().reset_index(), 'hospital_freq')
    results['tables']['city_freq'] = generate_table(df_copy['city'].value_counts().reset_index(), 'city_freq')
    results['tables']['mean_paid_by_disease'] = generate_table(df_copy.groupby('disease')['amount_paid'].mean().sort_values().reset_index(), 'mean_paid_by_disease')
    results['tables']['total_claim_by_city'] = generate_table(df_copy.groupby('city')['claim_amount'].sum().sort_values().reset_index(), 'total_claim_by_city')
    results['tables']['disease_category_stats'] = generate_table(df_copy.groupby('disease_category').agg({
        'claim_amount': ['mean', 'sum'],
        'id': 'count'
    }).reset_index(), 'disease_category_stats')
    # Add the pivot table data to the results
    # results['tables']['pivot_claims'] = pivot_html
    # results['data']['pivot_claims'] = hierarchy
    # results['data']['pivot_claims_columns'] = list(pivot_df.columns)

    if len(pivot_df) > 0: # Check if pivot_df has data
        # Get all column names from pivot_df
        results['data']['disease_category_counts'] = category_counts.to_dict('records')

        results['data']['pivot_claims_columns'] = list(pivot_df.columns) 
        results['data']['pivot_claims'] = hierarchy

        # Create a DataFrame for the main table with only hospital_name
        hospital_names_df = pivot_df.index.to_frame(name='hospital_name').reset_index(drop=True)
        results['tables']['pivot_claims'] = generate_table(hospital_names_df, 'pivot_claims')

    employee_paid = df_copy[df_copy['relationship'] == 'Employee']['amount_paid']
    spouse_paid = df_copy[df_copy['relationship'] == 'Spouse']['amount_paid']
    t_stat, p_val = ttest_ind(employee_paid.dropna(), spouse_paid.dropna())
    results['statistics']['hypothesis_test'] = {
        't_statistic': t_stat,
        'p_value': p_val
    }

    return results

def generate_table(df, table_id):
    return df.to_html(classes='display responsive nowrap', table_id=table_id, index=False, escape=False)

def plot_to_base64(fig):
    img = io.BytesIO()
    fig.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()
    plt.close(fig)
    return plot_url

def plot_age_distribution(df):
    plt.figure(figsize=(10, 5))
    df['age_at_admission'].plot(kind='hist', bins=20, title='Age at Admission')
    plt.gca().spines[['top', 'right']].set_visible(False)
    return plot_to_base64(plt.gcf())

def plot_amount_paid_vs_age(df):
    plt.figure(figsize=(10, 5))
    plt.scatter(df['age_at_admission'], df['amount_paid'], alpha=0.6, edgecolors="w", linewidth=0.5)
    plt.xlabel('Age at Admission')
    plt.ylabel('Amount Paid')
    plt.title('Amount Paid vs Age at Admission')
    return plot_to_base64(plt.gcf())

def plot_monthly_claims_trend(df):
    df['claim_month'] = df['created_date'].dt.to_period('M')
    monthly_claims = df.groupby('claim_month')['claim_amount'].agg(['count', 'mean']).reset_index()
    monthly_claims['claim_month'] = monthly_claims['claim_month'].astype(str)
    
    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax2 = ax1.twinx()
    
    ax1.plot(monthly_claims['claim_month'], monthly_claims['count'], color='blue', label='Count')
    ax2.plot(monthly_claims['claim_month'], monthly_claims['mean'], color='red', label='Mean')
    
    ax1.set_xlabel('Month')
    ax1.set_ylabel('Claim Count', color='blue')
    ax2.set_ylabel('Mean Claim Amount', color='red')
    
    plt.title('Monthly Claims Trend')
    fig.legend(loc="upper right", bbox_to_anchor=(1,1), bbox_transform=ax1.transAxes)
    
    plt.xticks(rotation=45)
    return plot_to_base64(fig)

def plot_daily_claims(df):
    df['admission_day'] = df['admission_date'].dt.dayofweek
    daily_claims = df.groupby('admission_day')['claim_amount'].agg(['count', 'mean']).reset_index()
    
    plt.figure(figsize=(10, 6))
    sns.barplot(x='admission_day', y='count', data=daily_claims)
    plt.title('Claim Count by Day of the Week')
    plt.xlabel('Day of the Week (0=Mon, 6=Sun)')
    plt.ylabel('Claim Count')
    return plot_to_base64(plt.gcf())

def plot_weekly_claim_creation(df):
    df['created_week'] = df['created_date'].dt.to_period('W')
    weekly_created_claims = df.groupby('created_week')['claim_amount'].agg(['count', 'mean']).reset_index()
    weekly_created_claims['created_week'] = weekly_created_claims['created_week'].dt.start_time
    
    plt.figure(figsize=(12, 6))
    sns.lineplot(x='created_week', y='count', data=weekly_created_claims, label='Claim Count')
    plt.title('Weekly Claim Creation Trend')
    plt.xlabel('Week')
    plt.ylabel('Count')
    plt.xticks(rotation=45)
    return plot_to_base64(plt.gcf())

def plot_weekly_admission(df):
    df['admission_week'] = df['admission_date'].dt.to_period('W')
    weekly_admissions = df.groupby('admission_week')['claim_amount'].agg(['count', 'mean']).reset_index()
    weekly_admissions['admission_week'] = weekly_admissions['admission_week'].dt.start_time
    
    plt.figure(figsize=(12, 6))
    sns.lineplot(x='admission_week', y='count', data=weekly_admissions, label='Admission Count')
    plt.title('Weekly Admission Trend')
    plt.xlabel('Week')
    plt.ylabel('Count')
    plt.xticks(rotation=45)
    return plot_to_base64(plt.gcf())

def plot_weekly_discharge(df):
    df['discharge_week'] = df['discharge_date'].dt.to_period('W')
    weekly_discharges = df.groupby('discharge_week')['claim_amount'].agg(['count', 'mean']).reset_index()
    weekly_discharges['discharge_week'] = weekly_discharges['discharge_week'].dt.start_time
    
    plt.figure(figsize=(12, 6))
    sns.lineplot(x='discharge_week', y='count', data=weekly_discharges, label='Discharge Count')
    plt.title('Weekly Discharge Trend')
    plt.xlabel('Week')
    plt.ylabel('Count')
    plt.xticks(rotation=45)
    return plot_to_base64(plt.gcf())

def plot_monthly_claim_creation(df):
    df['created_month'] = df['created_date'].dt.to_period('M')
    monthly_created_claims = df.groupby('created_month')['claim_amount'].agg(['count', 'mean']).reset_index()
    monthly_created_claims['created_month'] = monthly_created_claims['created_month'].dt.start_time
    
    plt.figure(figsize=(12, 6))
    sns.lineplot(x='created_month', y='count', data=monthly_created_claims, label='Claim Count')
    plt.title('Monthly Claim Creation Trend')
    plt.xlabel('Month')
    plt.ylabel('Count')
    plt.xticks(rotation=45)
    return plot_to_base64(plt.gcf())

def plot_monthly_admission(df):
    df['admission_month'] = df['admission_date'].dt.to_period('M')
    monthly_admissions = df.groupby('admission_month')['claim_amount'].agg(['count', 'mean']).reset_index()
    monthly_admissions['admission_month'] = monthly_admissions['admission_month'].dt.start_time
    
    plt.figure(figsize=(12, 6))
    sns.lineplot(x='admission_month', y='count', data=monthly_admissions, label='Admission Count')
    plt.title('Monthly Admission Trend')
    plt.xlabel('Month')
    plt.ylabel('Count')
    plt.xticks(rotation=45)
    return plot_to_base64(plt.gcf())

def plot_monthly_discharge(df):
    df['discharge_month'] = df['discharge_date'].dt.to_period('M')
    monthly_discharges = df.groupby('discharge_month')['claim_amount'].agg(['count', 'mean']).reset_index()
    monthly_discharges['discharge_month'] = monthly_discharges['discharge_month'].dt.start_time
    
    plt.figure(figsize=(12, 6))
    sns.lineplot(x='discharge_month', y='count', data=monthly_discharges, label='Discharge Count')
    plt.title('Monthly Discharge Trend')
    plt.xlabel('Month')
    plt.ylabel('Count')
    plt.xticks(rotation=45)
    return plot_to_base64(plt.gcf())

def plot_disease_category_distribution(df):
    category_counts = df['disease_category'].value_counts().reset_index()
    category_counts.columns = ['Category', 'Count']
    category_counts = category_counts.sort_values('Count', ascending=False)
    
    plt.figure(figsize=(12, 6))
    sns.barplot(x='Count', y='Category', data=category_counts.sort_values('Count', ascending=False))
    plt.title('Distribution of Disease Categories')
    plt.xlabel('Number of Claims')
    plt.ylabel('Disease Category')
    return plot_to_base64(plt.gcf()), category_counts.to_dict('records')

def display_disease_tests_table(df, category_df):
    # Get unique disease categories from the uploaded claims file
    categories_in_claims = df['disease_category'].unique()

    # Generate HTML table
    table_html = "<table id='disease-tests-table' class='display'>"
    table_html += "<thead><tr><th>Disease Category</th><th>Associated Tests</th></tr></thead>"
    table_html += "<tbody>"
    
    for category in categories_in_claims:
        tests = categorizer.get_tests(category)
        table_html += f"<tr><td>{category}</td><td>{tests}</td></tr>"
    
    table_html += "</tbody></table>"

    return table_html

if __name__ == '__main__':
    app.run(debug=True)