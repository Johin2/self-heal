"""Policy rule CRUD + evaluation."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import PolicyRule, Project
from app.policy_engine import evaluate as evaluate_rules
from app.projects import current_project
from app.schemas import (
    PolicyDecision,
    PolicyEvaluateRequest,
    PolicyRuleIn,
    PolicyRuleOut,
)
from app.security import authenticate_api_key

router = APIRouter(prefix="/v1/policy", tags=["policy"])


def _row_to_dict(rule: PolicyRule) -> dict:
    return {
        "id": str(rule.id),
        "name": rule.name,
        "enabled": rule.enabled,
        "priority": rule.priority,
        "conditions": rule.conditions,
        "action": rule.action,
    }


@router.get("", response_model=list[PolicyRuleOut])
async def list_rules(
    project: Project = Depends(current_project),
    session: AsyncSession = Depends(get_session),
) -> list[PolicyRuleOut]:
    rows = (
        await session.execute(
            select(PolicyRule)
            .where(PolicyRule.project_id == project.id)
            .order_by(PolicyRule.priority, PolicyRule.name)
        )
    ).scalars().all()
    return [PolicyRuleOut.model_validate(r) for r in rows]


@router.post("", response_model=PolicyRuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(
    body: PolicyRuleIn,
    project: Project = Depends(current_project),
    session: AsyncSession = Depends(get_session),
) -> PolicyRuleOut:
    row = PolicyRule(
        project_id=project.id,
        name=body.name,
        enabled=body.enabled,
        priority=body.priority,
        conditions=[c.model_dump() for c in body.conditions],
        action=body.action,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return PolicyRuleOut.model_validate(row)


@router.put("/{rule_id}", response_model=PolicyRuleOut)
async def update_rule(
    rule_id: uuid.UUID,
    body: PolicyRuleIn,
    project: Project = Depends(current_project),
    session: AsyncSession = Depends(get_session),
) -> PolicyRuleOut:
    stmt = select(PolicyRule).where(PolicyRule.id == rule_id, PolicyRule.project_id == project.id)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    row.name = body.name
    row.enabled = body.enabled
    row.priority = body.priority
    row.conditions = [c.model_dump() for c in body.conditions]
    row.action = body.action
    await session.commit()
    await session.refresh(row)
    return PolicyRuleOut.model_validate(row)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: uuid.UUID,
    project: Project = Depends(current_project),
    session: AsyncSession = Depends(get_session),
) -> None:
    await session.execute(
        delete(PolicyRule).where(PolicyRule.id == rule_id, PolicyRule.project_id == project.id)
    )
    await session.commit()


@router.post("/evaluate", response_model=PolicyDecision)
async def evaluate(
    body: PolicyEvaluateRequest,
    auth=Depends(authenticate_api_key),
    session: AsyncSession = Depends(get_session),
) -> PolicyDecision:
    _, project = auth
    rules = (
        await session.execute(
            select(PolicyRule).where(PolicyRule.project_id == project.id, PolicyRule.enabled.is_(True))
        )
    ).scalars().all()
    rule_dicts = [_row_to_dict(r) for r in rules]
    decision = evaluate_rules(body.event.model_dump(mode="json"), rule_dicts)
    return PolicyDecision(
        action=decision.action,  # type: ignore[arg-type]
        matched_rule_id=uuid.UUID(decision.matched_rule_id) if decision.matched_rule_id else None,
        matched_rule_name=decision.matched_rule_name,
    )


# Silence unused-import warning if `update` becomes unused later.
_ = update
