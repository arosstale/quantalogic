#!/usr/bin/env -S uv run

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "streamlit",
#     "yfinance",
#     "pandas",
#     "plotly",
#     "quantalogic",
# ]
# ///

import json
from datetime import datetime
from io import StringIO
from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

from quantalogic import Agent
from quantalogic.tools.tool import Tool, ToolArgument


class StreamlitInputTool(Tool):
    """Captures user input through Streamlit interface."""

    name: str = "input_tool"
    description: str = "Gets user input through Streamlit components"
    arguments: list[ToolArgument] = [
        ToolArgument(name="question", arg_type="string", description="Prompt for user", required=True)
    ]

    def execute(self, question: str) -> str:
        if "user_input" not in st.session_state:
            st.session_state.user_input = ""

        with st.form(key="input_form"):
            st.markdown(f"**{question}**")
            user_input = st.text_input("Your answer:", key="input_field")
            if st.form_submit_button("Submit") and user_input:
                st.session_state.user_input = user_input
                st.rerun()
        return st.session_state.user_input


class TechnicalAnalysisTool(Tool):
    """Computes technical indicators for stock analysis."""

    name: str = "technical_analysis_tool"
    description: str = "Calculates technical indicators (SMA, RSI) for stock analysis"
    arguments: list[ToolArgument] = [
        ToolArgument(name="symbol", arg_type="string", description="Stock symbol", required=True),
        ToolArgument(name="indicator", arg_type="string", description="Indicator type (sma|rsi)", required=True),
        ToolArgument(name="period", arg_type="int", description="Lookback period", required=True),
        ToolArgument(
            name="start_date",
            arg_type="string",
            description="Start date for data (YYYY-MM-DD)",
            required=False,
            default="2024-01-01",
        ),
        ToolArgument(
            name="end_date",
            arg_type="string",
            description="End date for data (YYYY-MM-DD)",
            required=False,
            default=datetime.now().strftime("%Y-%m-%d"),
        ),
    ]

    def execute(
        self, symbol: str, indicator: str, period: int, start_date: str = "2024-01-01", end_date: str = None
    ) -> str:
        try:
            # Use YFinanceTool to fetch historical data
            yfinance_tool = YFinanceTool()
            if end_date is None:
                end_date = datetime.now().strftime("%Y-%m-%d")

            # Fetch historical data
            data = yfinance_tool.execute(ticker=symbol, start_date=start_date, end_date=end_date)

            # Parse the JSON data
            df = pd.read_json(StringIO(data))
            df["Date"] = pd.to_datetime(df["Date"])

            if indicator.lower() == "sma":
                df[f"SMA_{period}"] = df["Close"].rolling(window=period).mean()
                result_col = f"SMA_{period}"
            elif indicator.lower() == "rsi":
                delta = df["Close"].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
                rs = gain / loss
                df["RSI"] = 100 - (100 / (1 + rs))
                result_col = "RSI"
            else:
                return "Unsupported indicator"

            # Display results
            st.subheader(f"{symbol.upper()} {indicator.upper()} ({period} days)")
            st.dataframe(df[["Date", "Close", result_col]])

            # Return the result as a JSON string for further processing
            return df[["Date", "Close", result_col]].to_json()
        except Exception as e:
            return f"Analysis error: {str(e)}"


class YFinanceTool(Tool):
    """Retrieves stock market data from Yahoo Finance."""

    name: str = "yfinance_tool"
    description: str = "Fetches historical stock data"
    arguments: list[ToolArgument] = [
        ToolArgument(name="ticker", arg_type="string", description="Stock symbol", required=True),
        ToolArgument(name="start_date", arg_type="string", description="Start date (YYYY-MM-DD)", required=True),
        ToolArgument(name="end_date", arg_type="string", description="End date (YYYY-MM-DD)", required=True),
    ]

    def execute(self, ticker: str, start_date: str, end_date: str) -> str:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(start=start_date, end=end_date)
            if not hist.empty:
                # Reset index to make Date a column and format decimals
                df = hist.reset_index()
                # Display the table in Streamlit
                st.subheader(f"{ticker} Historical Data")
                st.dataframe(
                    df.style.format(
                        {"Open": "{:.2f}", "High": "{:.2f}", "Low": "{:.2f}", "Close": "{:.2f}", "Volume": "{:,.0f}"}
                    ),
                    use_container_width=True,
                )
                return df.to_json(date_format="iso")
            return ""
        except Exception as e:
            return f"Data error: {str(e)}"


class VisualizationTool(Tool):
    """Generates interactive stock charts."""

    name: str = "visualization_tool"
    description: str = "Creates financial visualizations"
    arguments: list[ToolArgument] = [
        ToolArgument(name="data", arg_type="string", description="JSON historical data", required=True),
        ToolArgument(
            name="chart_type", arg_type="string", description="Chart style (line|candle|area)", required=False
        ),
        ToolArgument(name="caption", arg_type="string", description="Chart caption text", required=False),
    ]

    def execute(self, data: str, chart_type: str = "line", caption: Optional[str] = None) -> str:
        try:
            df = pd.read_json(StringIO(data))
            df["Date"] = pd.to_datetime(df["Date"])

            if chart_type == "candle":
                fig = go.Figure(
                    data=[
                        go.Candlestick(x=df["Date"], open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"])
                    ]
                )
            elif chart_type == "area":
                fig = px.area(df, x="Date", y="Close")
                fig.update_traces(fill="tozeroy")
            else:
                fig = px.line(df, x="Date", y="Close", markers=True)

            fig.update_layout(
                template="plotly_dark",
                xaxis_rangeslider_visible=chart_type == "candle",
                hovermode="x unified",
                title=caption if caption else None,
            )
            st.plotly_chart(fig, use_container_width=True)
            return "Graph displayed successfully"
        except Exception as e:
            return f"Viz error: {str(e)}"


def handle_stream_chunk(event: str, data: Optional[str] = None) -> None:
    if event == "stream_chunk" and data:
        if "response" not in st.session_state:
            st.session_state.response = ""
        st.session_state.response += data
        st.markdown(f"```\n{st.session_state.response}\n```")


def track_events(event: str, data: Optional[dict] = None) -> None:
    if event == "task_think_start":
        st.session_state.current_status = st.status("🔍 Analyzing query...", expanded=True)
    elif event == "tool_execution_start":
        with st.session_state.current_status:
            tool_name = data.get("tool_name", "Unknown tool")
            icon = "📊" if "viz" in tool_name.lower() else "💹"
            st.write(f"{icon} Executing {tool_name}")
    elif event == "task_think_end":
        st.session_state.current_status.update(label="✅ Analysis Complete", state="complete")


def main():
    st.set_page_config(page_title="Finance Suite Pro", layout="centered")
    st.title("📈 AI Financial Analyst")

    if "agent" not in st.session_state:
        st.session_state.agent = Agent(
            model_name="deepseek/deepseek-chat",
            tools=[StreamlitInputTool(), YFinanceTool(), VisualizationTool(), TechnicalAnalysisTool()],
        )

        # Configure event handlers properly
        st.session_state.agent.event_emitter.on(
            ["task_think_start", "tool_execution_start", "task_think_end"], track_events
        )
        st.session_state.agent.event_emitter.on(["stream_chunk"], handle_stream_chunk)

    query = st.chat_input("Ask financial questions (e.g., 'Show AAPL stock from 2020-2023 as candles')")

    if query:
        with st.spinner("Processing market data..."):
            try:
                result = st.session_state.agent.solve_task(f"Financial analysis request: {query}\n")

                # Result processing with markdown detection
                with st.container():
                    if result.startswith("```") and result.endswith("```"):
                        # Code block formatting
                        st.code(result.strip("```"), language="python")
                    elif any(md_char in result for md_char in ["#", "*", "`", "["]):
                        # Markdown content
                        st.markdown(result)
                    else:
                        # Plain text formatting
                        st.text(result)

            except Exception as e:
                st.error(f"Analysis failed: {str(e)}")
                st.exception(e)


if __name__ == "__main__":
    import sys

    import streamlit.web.cli as stcli

    if st.runtime.exists():
        main()
    else:
        sys.argv = ["streamlit", "run", __file__]
        sys.exit(stcli.main())
