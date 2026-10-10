"""mcp_server.py - M6: the mock inventory/ERP system, exposed as an MCP server.

Run standalone (stdio transport, for any MCP client to connect to):
  .venv/bin/python mcp_server.py

Tools:
  check_stock(asset_tag, asset_code, received_at, part_numbers)
      Read-only. Wraps facts.get_inventory_check (step 11) exactly - the
      same stock/reorder/lead-time view the deterministic pipeline already
      uses, just reachable by any MCP client, not only this project's code.

  raise_purchase_order(reference, part_number, quantity, raised_on, raised_by)
      Write. Creates a new PO for a part this class's inventory.json knows
      about. NEVER touches the original mock purchase_orders.json (that is
      exam data) - new POs go to procurement_log.json instead, gitignored,
      regenerable. Idempotent: the same (reference, part_number) always
      returns the SAME po_id, so a retried or re-run call never double-orders.

team.py's procurement_agent calls these same two tools in-process via
app.call_tool(...), so the agent and any external MCP client exercise the
exact same code path.
"""
import asyncio
import json
import logging
import uuid
from datetime import date, timedelta
from pathlib import Path

from mcp.server.mcpserver import MCPServer

import facts as F

logger = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
PROCUREMENT_LOG = HERE / "procurement_log.json"          # new POs this system has raised (mock ERP write)

app = MCPServer(name="plantguard-erp",
                description="Mock inventory/ERP system: stock checks and purchase-order creation.")


# ---------------------------------------------------------------------------
# Procurement log: a flat JSON list of POs this project has raised, separate
# from the original (read-only) purchase_orders.json dataset.
# ---------------------------------------------------------------------------
def _load_log() -> list[dict]:
    if PROCUREMENT_LOG.exists():
        return json.loads(PROCUREMENT_LOG.read_text())
    return []


def _save_log(entries: list[dict]) -> None:
    PROCUREMENT_LOG.write_text(json.dumps(entries, indent=1))


def _po_id(reference: str, part_number: str) -> str:
    """Stable id from (reference, part_number): the same call always yields the same PO (idempotent)."""
    digest = uuid.uuid5(uuid.NAMESPACE_URL, f"{reference}:{part_number}")
    return f"AGENT-PO-{str(digest)[:8].upper()}"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
@app.tool()
def check_stock(asset_tag: str, asset_code: str, received_at: str,
                part_numbers: list[str] | None = None) -> dict:
    """Stock, reorder point, lead time and open POs for this asset class's parts
    (facts.py step 11). Pass part_numbers to check specific parts; omit to see every
    part for the class."""
    lk = F.load_lookups()
    inv = F.get_inventory_check(lk, asset_tag, asset_code, received_at)
    if part_numbers:
        wanted = {p.strip().upper() for p in part_numbers}
        inv = {**inv, "parts": [p for p in inv["parts"] if p["part_number"] in wanted]}
    return inv


@app.tool()
def raise_purchase_order(reference: str, part_number: str, quantity: int,
                         raised_on: str, raised_by: str = "procurement_agent") -> dict:
    """Create a PO for `quantity` units of `part_number`. `reference` is the
    triage record_id this order is for (used for the idempotency key, so
    re-calling with the same reference+part_number returns the existing PO,
    never a duplicate). Looks up unit_cost_inr and lead_time_days from
    inventory.json, and reuses the supplier_id of this part's most recent
    prior PO if one exists (else "UNKNOWN": no supplier on file yet)."""
    po_id = _po_id(reference, part_number)
    log = _load_log()
    existing = next((p for p in log if p["po_id"] == po_id), None)
    if existing:
        logger.info("MCP: raise_purchase_order %s is already on file (idempotent)", po_id)
        return {**existing, "created": False}

    lk = F.load_lookups()
    part = next((p for code_parts in lk["inventory"].values() for p in code_parts
                if p["part_number"] == part_number), None)
    if part is None:
        return {"error": f"unknown part_number {part_number!r}"}

    prior = lk["purchase_orders"].get(part_number, [])
    supplier_id = prior[-1]["supplier_id"] if prior else "UNKNOWN"
    unit_cost = part["unit_cost_inr"]
    delivery = (date.fromisoformat(raised_on) + timedelta(days=part["lead_time_days"])).isoformat()

    po = {
        "po_id": po_id, "reference": reference, "part_number": part_number,
        "supplier_id": supplier_id, "quantity": quantity, "unit_cost_inr": unit_cost,
        "total_inr": unit_cost * quantity, "raised_on": raised_on,
        "expected_delivery_on": delivery, "received_on": None, "status": "requested",
        "raised_by": raised_by,
    }
    log.append(po)
    _save_log(log)
    logger.info("MCP: raised PO %s for %dx %s (delivery by %s)", po_id, quantity, part_number, delivery)
    return {**po, "created": True}


# ---------------------------------------------------------------------------
# In-process call, for team.py's procurement_agent (no subprocess needed -
# exercises the exact same tool code a real MCP client over stdio would hit)
# ---------------------------------------------------------------------------
def call_tool_sync(name: str, arguments: dict) -> dict:
    """Run an MCP tool call synchronously and return its structured result."""
    result = asyncio.run(app.call_tool(name, arguments))
    content = result.structured_content if hasattr(result, "structured_content") else None
    return content if content is not None else json.loads(result.content[0].text)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app.run("stdio")
