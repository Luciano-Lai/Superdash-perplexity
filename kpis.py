    st.markdown(
        f"""
        <div style="
            background-color: {background};
            border: 1px solid #E5E7EB;
            border-left: 5px solid {color};
            border-radius: 12px;
            padding: 18px 20px;
            height: 130px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        ">
            <div style="
                font-size: 0.78rem;
                font-weight: 600;
                color: #6B7280;
                text-transform: uppercase;
                letter-spacing: 0.03em;
                margin-bottom: 8px;
            ">
                {icon} {kpi_name}
            </div>

            <div style="
                font-size: 1.65rem;
                font-weight: 700;
                color: {color};
                line-height: 1.15;
            ">
                {value_text}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
