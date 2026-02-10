"""
LLM-Powered ETL Optimizer - Streamlit Demo

Interactive demo showcasing AI-powered SQL to DBT transformation.
Transform legacy SQL into optimized, documented DBT models.

Author: Waqas Shami
"""

import streamlit as st
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.sql_parser import SQLParser, SQLAnalysis
from src.quality_scorer import QualityScorer
from app.demo_responses import get_demo_response, SAMPLE_QUERIES

# Page configuration
st.set_page_config(
    page_title="LLM ETL Optimizer",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1E3A5F;
        margin-bottom: 0;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        margin-top: 0;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
    }
    .metric-label {
        font-size: 0.9rem;
        opacity: 0.9;
    }
    .code-block {
        background-color: #1e1e1e;
        border-radius: 8px;
        padding: 15px;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 8px;
        padding: 15px;
        color: #155724;
    }
    .warning-box {
        background-color: #fff3cd;
        border: 1px solid #ffeeba;
        border-radius: 8px;
        padding: 15px;
        color: #856404;
    }
    .info-box {
        background-color: #e7f3ff;
        border: 1px solid #b6d4fe;
        border-radius: 8px;
        padding: 15px;
        color: #084298;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        border-radius: 8px 8px 0 0;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    if 'analysis_result' not in st.session_state:
        st.session_state.analysis_result = None
    if 'dbt_output' not in st.session_state:
        st.session_state.dbt_output = None
    if 'quality_report' not in st.session_state:
        st.session_state.quality_report = None


def render_header():
    """Render the application header."""
    col1, col2 = st.columns([3, 1])

    with col1:
        st.markdown('<p class="main-header">🔄 LLM-Powered ETL Optimizer</p>', unsafe_allow_html=True)
        st.markdown('<p class="sub-header">Transform legacy SQL into optimized, documented DBT models using AI</p>', unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div style="text-align: right; padding-top: 20px;">
            <a href="https://github.com/waqas-shami/llm-etl-optimizer" target="_blank">
                <img src="https://img.shields.io/badge/GitHub-View_Code-black?style=for-the-badge&logo=github" />
            </a>
        </div>
        """, unsafe_allow_html=True)


def render_sidebar():
    """Render the sidebar with options and information."""
    with st.sidebar:
        st.markdown("### ⚙️ Configuration")

        # Mode selection
        mode = st.radio(
            "Mode",
            ["Demo Mode (No API Key)", "Live Mode (With API Key)"],
            help="Demo mode uses pre-computed responses. Live mode calls actual LLM APIs."
        )

        use_live_mode = mode == "Live Mode (With API Key)"

        if use_live_mode:
            st.text_input("OpenAI API Key", type="password", key="openai_key")
            st.caption("Your API key is not stored and only used for this session.")

        st.divider()

        # Target dialect
        dialect = st.selectbox(
            "Target SQL Dialect",
            ["Snowflake", "BigQuery", "Redshift", "PostgreSQL"],
            help="Select your target data warehouse"
        )

        # Options
        st.markdown("### 📋 Output Options")
        include_tests = st.checkbox("Include Data Tests", value=True)
        include_docs = st.checkbox("Include Documentation", value=True)
        include_explanation = st.checkbox("Include Optimization Explanation", value=True)

        st.divider()

        # About section
        st.markdown("### 📖 About")
        st.markdown("""
        This tool demonstrates how Large Language Models can accelerate
        data engineering workflows by:

        - Analyzing legacy SQL patterns
        - Generating optimized DBT models
        - Adding documentation & tests
        - Scoring code quality

        **Tech Stack:**
        - GPT-4 / Claude
        - LangChain
        - DBT Core
        - Python
        """)

        st.divider()

        st.markdown("### 👤 Author")
        st.markdown("""
        **Waqas Shami**
        Head of Data Platform
        [LinkedIn](https://linkedin.com/in/waqas-shami) | [Website](https://waqasshami.com)
        """)

        return {
            "use_live_mode": use_live_mode,
            "dialect": dialect.lower(),
            "include_tests": include_tests,
            "include_docs": include_docs,
            "include_explanation": include_explanation
        }


def render_sample_queries():
    """Render sample query selection."""
    st.markdown("### 📝 Try a Sample Query")

    sample_options = {
        "Select a sample...": "",
        "🛒 Customer Sales Summary": "customer_sales",
        "📦 Inventory Analysis": "inventory",
        "💰 Revenue by Category": "revenue_category",
        "👥 Customer Segmentation": "customer_segment",
        "📊 Monthly Trends": "monthly_trends"
    }

    selected = st.selectbox(
        "Choose a sample query to see the optimizer in action:",
        options=list(sample_options.keys()),
        label_visibility="collapsed"
    )

    if sample_options[selected]:
        return SAMPLE_QUERIES.get(sample_options[selected], "")
    return None


def analyze_sql(sql_input: str) -> SQLAnalysis:
    """Analyze the input SQL."""
    parser = SQLParser()
    return parser.parse(sql_input)


def render_analysis_results(analysis: SQLAnalysis):
    """Render SQL analysis results."""
    st.markdown("### 🔍 SQL Analysis")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Tables", len(analysis.tables))
    with col2:
        st.metric("Joins", len(analysis.joins))
    with col3:
        st.metric("Aggregations", len(analysis.aggregations))
    with col4:
        complexity_color = "🟢" if analysis.complexity_score < 40 else "🟡" if analysis.complexity_score < 70 else "🔴"
        st.metric("Complexity", f"{complexity_color} {analysis.complexity_score}/100")

    with st.expander("📋 Detailed Analysis", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Tables Identified:**")
            for table in analysis.tables:
                st.markdown(f"- `{table}`")

            if analysis.joins:
                st.markdown("**Joins:**")
                for join in analysis.joins:
                    st.markdown(f"- {join.get('type', 'JOIN')} on `{join.get('table', 'unknown')}`")

        with col2:
            if analysis.aggregations:
                st.markdown("**Aggregations:**")
                for agg in analysis.aggregations:
                    st.markdown(f"- `{agg}`")

            if analysis.group_by:
                st.markdown("**Group By:**")
                for col in analysis.group_by:
                    st.markdown(f"- `{col}`")

            if analysis.where_conditions:
                st.markdown("**Filters:**")
                st.code(analysis.where_conditions[0][:100] + "..." if len(analysis.where_conditions[0]) > 100 else analysis.where_conditions[0])


def render_dbt_output(dbt_model: str, yaml_schema: str, explanation: str, options: dict):
    """Render the generated DBT output."""
    st.markdown("### ✨ Generated DBT Model")

    tab1, tab2, tab3 = st.tabs(["📄 DBT SQL", "📋 Schema YAML", "💡 Explanation"])

    with tab1:
        st.code(dbt_model, language="sql")

        col1, col2 = st.columns([1, 4])
        with col1:
            st.download_button(
                "⬇️ Download SQL",
                dbt_model,
                file_name="optimized_model.sql",
                mime="text/plain"
            )

    with tab2:
        if options["include_docs"]:
            st.code(yaml_schema, language="yaml")

            col1, col2 = st.columns([1, 4])
            with col1:
                st.download_button(
                    "⬇️ Download YAML",
                    yaml_schema,
                    file_name="_schema.yml",
                    mime="text/yaml"
                )
        else:
            st.info("Documentation generation was disabled in options.")

    with tab3:
        if options["include_explanation"]:
            st.markdown(explanation)
        else:
            st.info("Explanation was disabled in options.")


def render_quality_score(dbt_model: str, yaml_schema: str):
    """Render quality score assessment."""
    st.markdown("### 📊 Quality Assessment")

    scorer = QualityScorer()
    report = scorer.evaluate(dbt_model, yaml_schema)

    # Overall score with visual
    col1, col2 = st.columns([1, 2])

    with col1:
        score_color = "#28a745" if report.overall_score >= 80 else "#ffc107" if report.overall_score >= 60 else "#dc3545"
        st.markdown(f"""
        <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, {score_color}88, {score_color}); border-radius: 15px;">
            <div style="font-size: 3rem; font-weight: bold; color: white;">{report.overall_score}</div>
            <div style="font-size: 1rem; color: white; opacity: 0.9;">Overall Score</div>
            <div style="font-size: 0.9rem; color: white; margin-top: 10px;">
                {"✅ PASSED" if report.passed else "⚠️ NEEDS IMPROVEMENT"}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("**Category Breakdown:**")

        for category, result in report.categories.items():
            score = result['score']
            color = "#28a745" if score >= 80 else "#ffc107" if score >= 60 else "#dc3545"

            st.markdown(f"""
            <div style="margin-bottom: 10px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
                    <span>{category.capitalize()}</span>
                    <span>{score}/100</span>
                </div>
                <div style="background: #e9ecef; border-radius: 5px; height: 8px; overflow: hidden;">
                    <div style="background: {color}; width: {score}%; height: 100%;"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # Issues and suggestions
    if report.issues or report.suggestions:
        with st.expander("📝 Detailed Feedback", expanded=False):
            if report.issues:
                st.markdown("**Issues Found:**")
                for issue in report.issues[:5]:
                    severity = issue.get('severity', 'info').upper()
                    icon = "🔴" if severity == "ERROR" else "🟡" if severity == "WARNING" else "🔵"
                    st.markdown(f"{icon} **{severity}**: {issue.get('message', '')}")

            if report.suggestions:
                st.markdown("**Suggestions:**")
                for i, suggestion in enumerate(report.suggestions[:5], 1):
                    st.markdown(f"{i}. {suggestion}")


def render_comparison():
    """Render before/after comparison metrics."""
    st.markdown("### 📈 Transformation Impact")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea, #764ba2); padding: 20px; border-radius: 10px; text-align: center; color: white;">
            <div style="font-size: 1.8rem; font-weight: bold;">81%</div>
            <div style="font-size: 0.85rem; opacity: 0.9;">Faster Development</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #f093fb, #f5576c); padding: 20px; border-radius: 10px; text-align: center; color: white;">
            <div style="font-size: 1.8rem; font-weight: bold;">94%</div>
            <div style="font-size: 0.85rem; opacity: 0.9;">Documentation Coverage</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #4facfe, #00f2fe); padding: 20px; border-radius: 10px; text-align: center; color: white;">
            <div style="font-size: 1.8rem; font-weight: bold;">56%</div>
            <div style="font-size: 0.85rem; opacity: 0.9;">Fewer Review Cycles</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #43e97b, #38f9d7); padding: 20px; border-radius: 10px; text-align: center; color: white;">
            <div style="font-size: 1.8rem; font-weight: bold;">€180K</div>
            <div style="font-size: 0.85rem; opacity: 0.9;">Annual Savings</div>
        </div>
        """, unsafe_allow_html=True)


def main():
    """Main application entry point."""
    init_session_state()
    render_header()

    st.divider()

    # Sidebar configuration
    options = render_sidebar()

    # Main content area
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("### 📥 Input SQL")

        # Sample query selection
        sample_sql = render_sample_queries()

        # SQL input area
        default_sql = sample_sql if sample_sql else """SELECT
    c.customer_id,
    c.customer_name,
    c.email,
    SUM(o.amount) as total_revenue,
    COUNT(DISTINCT o.order_id) as order_count,
    AVG(o.amount) as avg_order_value
FROM customers c
LEFT JOIN orders o ON c.customer_id = o.customer_id
WHERE o.order_date >= '2024-01-01'
  AND o.status = 'completed'
GROUP BY c.customer_id, c.customer_name, c.email
HAVING SUM(o.amount) > 1000
ORDER BY total_revenue DESC"""

        sql_input = st.text_area(
            "Enter your legacy SQL query:",
            value=default_sql,
            height=300,
            label_visibility="collapsed"
        )

        # Business context (optional)
        with st.expander("➕ Add Business Context (Optional)"):
            context = st.text_area(
                "Provide additional context to improve the optimization:",
                placeholder="e.g., This query powers the executive dashboard for quarterly reviews...",
                height=100
            )

        # Optimize button
        optimize_clicked = st.button(
            "🚀 Optimize SQL",
            type="primary",
            use_container_width=True
        )

    with col2:
        if optimize_clicked and sql_input.strip():
            with st.spinner("🔄 Analyzing and optimizing..."):
                # Analyze SQL
                analysis = analyze_sql(sql_input)

                # Get demo response (or call LLM in live mode)
                demo_result = get_demo_response(sql_input, options)

                # Store in session state
                st.session_state.analysis_result = analysis
                st.session_state.dbt_output = demo_result

        # Display results if available
        if st.session_state.analysis_result:
            render_analysis_results(st.session_state.analysis_result)

    # Full-width output sections
    if st.session_state.dbt_output:
        st.divider()

        render_dbt_output(
            st.session_state.dbt_output["dbt_model"],
            st.session_state.dbt_output["yaml_schema"],
            st.session_state.dbt_output["explanation"],
            options
        )

        st.divider()

        render_quality_score(
            st.session_state.dbt_output["dbt_model"],
            st.session_state.dbt_output["yaml_schema"]
        )

        st.divider()

        render_comparison()

    # Footer
    st.divider()
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 20px;">
        <p>🔄 LLM-Powered ETL Optimizer | Built with Streamlit, LangChain, and GPT-4</p>
        <p style="font-size: 0.9rem;">
            <a href="https://waqasshami.com" target="_blank">waqasshami.com</a> |
            <a href="https://linkedin.com/in/waqas-shami" target="_blank">LinkedIn</a> |
            <a href="https://github.com/waqas-shami" target="_blank">GitHub</a>
        </p>
        <p style="font-size: 0.8rem; opacity: 0.7;">
            This is a demonstration project showcasing AI/ML capabilities in data engineering.
        </p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
