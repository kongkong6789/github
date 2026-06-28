from __future__ import annotations

from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph


class EcommerceState(TypedDict):
    task: str
    route: Literal["listing", "ads", "listing_ads", "research", "general"]
    research: str
    listing: str
    ads: str
    review: str
    final: str


def supervisor(state: EcommerceState) -> dict:
    task = state["task"].lower()
    wants_listing = any(word in task for word in ["listing", "标题", "五点", "描述", "文案"])
    wants_ads = any(word in task for word in ["广告", "acos", "roas", "关键词", "投放"])
    if wants_listing and wants_ads:
        route = "listing_ads"
    elif wants_listing:
        route = "listing"
    elif wants_ads:
        route = "ads"
    elif any(word in task for word in ["竞品", "调研", "市场", "选品"]):
        route = "research"
    else:
        route = "general"
    return {"route": route}


def research_agent(state: EcommerceState) -> dict:
    task = state["task"]
    return {
        "research": (
            "市场调研 Agent：围绕任务「{task}」先看竞品价格、主图卖点、差评痛点、"
            "搜索关键词和平台规则，再给后续 Agent 提供依据。"
        ).format(task=task)
    }


def listing_agent(state: EcommerceState) -> dict:
    research = state.get("research", "")
    return {
        "listing": (
            "Listing Agent：基于调研结果，产出标题、五点描述、A+ 页面结构和合规提醒。\n"
            f"依据：{research}"
        )
    }


def ads_agent(state: EcommerceState) -> dict:
    research = state.get("research", "")
    return {
        "ads": (
            "广告 Agent：拆分品牌词、品类词、长尾词，给出预算、否词、竞价和 ACOS 优化建议。\n"
            f"依据：{research}"
        )
    }


def review_agent(state: EcommerceState) -> dict:
    parts = [
        state.get("research", ""),
        state.get("listing", ""),
        state.get("ads", ""),
    ]
    useful_parts = [part for part in parts if part]
    review = "审核 Agent：检查是否有夸大宣传、违规词、价格异常和需要人工确认的操作。"
    final = "\n\n".join(useful_parts + [review])
    return {"review": review, "final": final}


def route_after_supervisor(state: EcommerceState) -> str:
    if state["route"] == "listing":
        return "research_agent"
    if state["route"] == "ads":
        return "research_agent"
    if state["route"] == "research":
        return "research_agent"
    return "research_agent"


def route_after_research(state: EcommerceState) -> str:
    if state["route"] in ["listing", "listing_ads"]:
        return "listing_agent"
    if state["route"] == "ads":
        return "ads_agent"
    return "review_agent"


def route_after_listing(state: EcommerceState) -> str:
    if state["route"] == "listing_ads":
        return "ads_agent"
    return "review_agent"


def build_graph():
    graph = StateGraph(EcommerceState)
    graph.add_node("supervisor", supervisor)
    graph.add_node("research_agent", research_agent)
    graph.add_node("listing_agent", listing_agent)
    graph.add_node("ads_agent", ads_agent)
    graph.add_node("review_agent", review_agent)

    graph.set_entry_point("supervisor")
    graph.add_conditional_edges("supervisor", route_after_supervisor)
    graph.add_conditional_edges("research_agent", route_after_research)
    graph.add_conditional_edges("listing_agent", route_after_listing)
    graph.add_edge("ads_agent", "review_agent")
    graph.add_edge("review_agent", END)
    return graph.compile()


def run_mock_demo(task: str) -> str:
    app = build_graph()
    result = app.invoke(
        {
            "task": task,
            "route": "general",
            "research": "",
            "listing": "",
            "ads": "",
            "review": "",
            "final": "",
        }
    )
    return result["final"]
