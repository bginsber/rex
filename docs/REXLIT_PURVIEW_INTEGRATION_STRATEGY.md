# RexLit + Microsoft Purview Integration Strategy

**Last Updated:** 2025-11-20
**RexLit Version:** v0.2.0-m1
**Target Purview Version:** Microsoft Purview with DSPM for AI (2025)

## Executive Summary

This document outlines strategies for integrating RexLit's unique offline-first eDiscovery capabilities with Microsoft Purview's cloud-based compliance platform. By combining RexLit's strengths (Bates stamping, offline processing, deterministic workflows, LLM-powered privilege classification) with Purview's enterprise scale and Microsoft 365 integration, organizations can achieve a **hybrid eDiscovery architecture** that addresses limitations in both platforms.

**Key Integration Value Propositions:**
1. **Add Bates stamping** to Purview workflows (currently missing)
2. **Enable offline processing** for air-gapped review rooms
3. **Provide deterministic, reproducible** document processing
4. **Enhance privilege classification** with RexLit's LLM-powered models
5. **Bridge on-premises and cloud** eDiscovery workflows
6. **Reduce costs** by offloading processing to local RexLit instances

---

## Table of Contents

1. [Integration Approaches Overview](#1-integration-approaches-overview)
2. [Approach A: RexLit as a Purview GenAI Application](#2-approach-a-rexlit-as-a-purview-genai-application)
3. [Approach B: RexLit as an External Data Source](#3-approach-b-rexlit-as-an-external-data-source)
4. [Approach C: Hybrid Processing Architecture](#4-approach-c-hybrid-processing-architecture)
5. [Approach D: Feature-Specific Integrations](#5-approach-d-feature-specific-integrations)
6. [Technical Implementation Details](#6-technical-implementation-details)
7. [Microsoft Graph API Integration](#7-microsoft-graph-api-integration)
8. [DSPM for AI Configuration for RexLit](#8-dspm-for-ai-configuration-for-rexlit)
9. [Security and Compliance Considerations](#9-security-and-compliance-considerations)
10. [Cost-Benefit Analysis](#10-cost-benefit-analysis)
11. [Implementation Roadmap](#11-implementation-roadmap)
12. [Use Cases and Examples](#12-use-cases-and-examples)

---

## 1. Integration Approaches Overview

### The Gap Analysis

**Microsoft Purview Limitations:**
- ❌ No Bates stamping capability
- ❌ No offline processing mode
- ❌ Limited to Microsoft 365 data sources
- ❌ No deterministic processing guarantees
- ❌ Generic LLM support (Security Copilot), not privilege-specific

**RexLit Limitations:**
- ❌ No real-time legal holds on cloud data
- ❌ Limited scale (100K documents vs. millions)
- ❌ No direct Microsoft 365 API access
- ❌ Minimal collaboration features
- ❌ No enterprise RBAC

### Integration Strategy Matrix

| Approach | Complexity | Value Delivered | Primary Use Case |
|----------|-----------|-----------------|------------------|
| **A: GenAI App** | Low-Medium | Privilege classification monitoring | Audit RexLit's LLM privilege decisions in Purview |
| **B: Data Source** | Medium | Unified audit trail | Centralize RexLit processing logs in Purview |
| **C: Hybrid Architecture** | High | Complete workflow coverage | Offline processing + cloud collaboration |
| **D: Feature Modules** | Medium-High | Specific capability gaps | Add Bates stamping to Purview productions |

**Recommended Primary Approach:** **Approach C (Hybrid Architecture)** with selective use of Approach A for LLM monitoring.

---

## 2. Approach A: RexLit as a Purview GenAI Application

### Overview

Register RexLit's LLM-powered privilege classification as a **custom GenAI application** in Microsoft Purview DSPM for AI. This allows Purview to:
- Monitor prompts sent to Groq/OpenAI for privilege decisions
- Detect sensitive information in privilege review workflows
- Apply Communication Compliance policies to privilege decisions
- Calculate insider risk scores for potentially risky privilege classifications

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Microsoft Purview DSPM for AI                           │
│  ┌──────────────────────────────────────────┐           │
│  │ KYD Policy: "RexLit Privilege AI"        │           │
│  │ - Collect prompts/responses              │           │
│  │ - Detect sensitive info                  │           │
│  │ - Apply compliance policies              │           │
│  └──────────────────────────────────────────┘           │
│           ↑ Microsoft Purview API                       │
└───────────┼─────────────────────────────────────────────┘
            │
            │ Prompt/Response Logging
            │
┌───────────┼─────────────────────────────────────────────┐
│ RexLit Privilege Classification Service                 │
│  ┌──────────────────────────────────────────┐           │
│  │ Pattern Pre-Filtering (85%+ confidence)  │           │
│  └──────────────────────────────────────────┘           │
│           ↓ Uncertain cases (50-84%)                    │
│  ┌──────────────────────────────────────────┐           │
│  │ LLM Escalation (Groq/OpenAI)             │           │
│  │ → Log to Purview API                     │ ← NEW     │
│  └──────────────────────────────────────────┘           │
│  ┌──────────────────────────────────────────┐           │
│  │ Local Audit (SHA-256 hash chain)         │           │
│  └──────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────┘
```

### Implementation Steps

#### Step 1: Register RexLit as an Entra ID Application

```bash
# Create Entra ID app registration for RexLit
az ad app create \
  --display-name "RexLit Privilege Classification" \
  --identifier-uris "api://rexlit-privilege" \
  --required-resource-accesses @manifest.json
```

**Required Microsoft Graph API Permissions:**
- `InformationProtection.Read.All` - Read sensitivity labels
- `PrivilegeManagement.ReadWrite.All` - Access Purview privilege APIs (if available)
- `AuditLog.ReadWrite.All` - Write to Purview audit log

#### Step 2: Create DSPM for AI KYD Policy via PowerShell

```powershell
# Connect to Security & Compliance PowerShell
Connect-IPPSSession -UserPrincipalName admin@contoso.com

# Create collection policy for RexLit privilege classification
New-FeatureConfiguration `
  -FeatureScenario KnowYourData `
  -Name "DSPM for AI - RexLit Privilege Classification" `
  -Mode Enable `
  -ScenarioConfig '{
    "Activities": ["UploadText", "DownloadText"],
    "EnforcementPlanes": ["Entra"],
    "SensitiveTypeIds": ["All"],
    "IsIngestionEnabled": true
  }' `
  -Locations '[{
    "Workload": "Applications",
    "Location": "ee1680d0-702f-4090-b26c-c49091e86531",
    "LocationSource": "Entra",
    "LocationType": "Group",
    "Inclusions": [{
      "Type": "Tenant",
      "Identity": "All"
    }]
  }]'
```

#### Step 3: Create Compliance Policies

**Communication Compliance Policy:**
```powershell
# Detect unethical behavior in RexLit privilege decisions
New-CommunicationCompliancePolicy `
  -Name "RexLit Privilege Review Monitoring" `
  -Description "Monitor privilege classification prompts for inappropriate content" `
  -Scope "ApplicationId:rexlit-privilege" `
  -Conditions @{
    SensitiveInformationTypes = @("All")
    UnethicalLanguage = $true
  }
```

**Insider Risk Management Policy:**
```powershell
# Calculate risk scores for privilege decisions
New-InsiderRiskPolicy `
  -Name "RexLit Risky Privilege Usage" `
  -Description "Detect risky prompts in privilege classification workflows" `
  -PolicyTemplate "RiskyAIUsage" `
  -Scope "ApplicationId:rexlit-privilege"
```

#### Step 4: Modify RexLit to Call Purview API

Add a new adapter: `rexlit/app/adapters/purview_audit_adapter.py`

```python
"""Microsoft Purview audit logging adapter for RexLit privilege classification."""

import os
from typing import Protocol
from dataclasses import dataclass
from datetime import datetime
import httpx
from azure.identity import DefaultAzureCredential

@dataclass
class PurviewAIInteraction:
    """Represents an AI interaction logged to Purview."""
    app_id: str
    user_id: str
    prompt: str
    response: str
    timestamp: datetime
    sensitive_types: list[str]
    metadata: dict


class PurviewAuditPort(Protocol):
    """Port for logging to Microsoft Purview DSPM for AI."""

    def log_ai_interaction(self, interaction: PurviewAIInteraction) -> None:
        """Log an AI interaction to Purview."""
        ...


class MicrosoftPurviewAuditAdapter:
    """Concrete adapter for Microsoft Purview API integration."""

    def __init__(self, tenant_id: str, app_id: str):
        self.tenant_id = tenant_id
        self.app_id = app_id
        self.credential = DefaultAzureCredential()
        self.graph_endpoint = "https://graph.microsoft.com/v1.0"

    def log_ai_interaction(self, interaction: PurviewAIInteraction) -> None:
        """Send privilege classification to Purview DSPM for AI."""

        # Get access token
        token = self.credential.get_token(
            "https://graph.microsoft.com/.default"
        ).token

        # Prepare payload
        payload = {
            "aiInteraction": {
                "applicationId": self.app_id,
                "userId": interaction.user_id,
                "prompt": {
                    "content": interaction.prompt,
                    "timestamp": interaction.timestamp.isoformat()
                },
                "response": {
                    "content": interaction.response,
                    "timestamp": datetime.utcnow().isoformat()
                },
                "sensitiveInformationTypes": interaction.sensitive_types,
                "metadata": interaction.metadata
            }
        }

        # Send to Purview API
        with httpx.Client() as client:
            response = client.post(
                f"{self.graph_endpoint}/security/purview/aiInteractions",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=30.0
            )
            response.raise_for_status()
```

#### Step 5: Wire into Privilege Service

Modify `rexlit/app/privilege_service.py`:

```python
class PrivilegeService:
    def __init__(
        self,
        privilege_port: PrivilegePort,
        ledger: LedgerPort,
        purview_audit: Optional[PurviewAuditPort] = None,  # NEW
    ):
        self.privilege_port = privilege_port
        self.ledger = ledger
        self.purview_audit = purview_audit  # NEW

    async def classify_document(
        self, doc_path: Path, content: str
    ) -> PrivilegeDecision:
        """Classify document with optional Purview logging."""

        # Run privilege classification
        decision = await self.privilege_port.classify(content)

        # Log to local audit trail
        self.ledger.append({
            "event": "privilege.classify",
            "document": str(doc_path),
            "decision": decision.classification,
            "confidence": decision.confidence,
        })

        # NEW: Log to Purview if configured
        if self.purview_audit and decision.confidence < 0.85:
            # Only log LLM escalations (uncertain cases)
            self.purview_audit.log_ai_interaction(
                PurviewAIInteraction(
                    app_id=os.getenv("REXLIT_PURVIEW_APP_ID"),
                    user_id=os.getenv("USER", "unknown"),
                    prompt=self._build_privilege_prompt(content),
                    response=decision.rationale,
                    timestamp=datetime.utcnow(),
                    sensitive_types=decision.detected_entities,
                    metadata={
                        "document": str(doc_path),
                        "confidence": decision.confidence,
                        "classification": decision.classification,
                    }
                )
            )

        return decision
```

### Validation and Monitoring

After configuration, validate in Purview portal:

1. **Reports → DSPM for AI → Activity Explorer**
   - Filter by app: "RexLit Privilege Classification"
   - View prompts, responses, and sensitive detections

2. **Communication Compliance**
   - Review policy: "RexLit Privilege Review Monitoring"
   - Investigate any flagged privilege decisions

3. **Insider Risk Management**
   - Monitor risk scores for users running privilege classification
   - Alert on unusual privilege review patterns

### Benefits

- ✅ **Compliance oversight** of RexLit's LLM usage
- ✅ **Sensitive data detection** in privilege review workflows
- ✅ **Risk scoring** for potentially inappropriate privilege decisions
- ✅ **Unified audit trail** across RexLit and Purview
- ✅ **No disruption** to RexLit's offline-first design (Purview logging is optional)

### Limitations

- ⚠️ Requires online mode for Purview API calls (conflicts with offline-first design)
- ⚠️ Adds latency to privilege classification (~200-500ms per API call)
- ⚠️ Increases complexity (Azure AD auth, API credentials)
- ⚠️ Partial logging (only LLM escalations, not pattern-based filtering)

---

## 3. Approach B: RexLit as an External Data Source

### Overview

Configure RexLit to export audit logs, search results, and production metadata to Microsoft Purview as an **external data source**. This enables:
- Centralized audit trail across on-prem and cloud workflows
- Purview eDiscovery searches over RexLit-processed documents
- Unified compliance reporting

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Microsoft Purview eDiscovery                            │
│  ┌──────────────────────────────────────────┐           │
│  │ Case: "Matter 2025-001"                  │           │
│  │  ├─ Microsoft 365 Custodians (native)    │           │
│  │  ├─ RexLit External Data Source          │ ← NEW     │
│  │  └─ Unified Search Results               │           │
│  └──────────────────────────────────────────┘           │
│           ↑ Microsoft Graph API                         │
└───────────┼─────────────────────────────────────────────┘
            │
            │ Metadata Export (JSONL → Graph API)
            │
┌───────────┼─────────────────────────────────────────────┐
│ RexLit (On-Premises)                                    │
│  ┌──────────────────────────────────────────┐           │
│  │ Local Processing                         │           │
│  │  ├─ Ingest, Index, OCR, Bates           │           │
│  │  └─ Audit Log (SHA-256 hash chain)      │           │
│  └──────────────────────────────────────────┘           │
│           ↓                                             │
│  ┌──────────────────────────────────────────┐           │
│  │ Purview Export Adapter                   │ ← NEW     │
│  │  ├─ Convert JSONL → Graph API format    │           │
│  │  ├─ Upload document metadata             │           │
│  │  └─ Sync Bates numbers to Purview       │           │
│  └──────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────┘
```

### Implementation Steps

#### Step 1: Create Purview Export Adapter

`rexlit/app/adapters/purview_export_adapter.py`:

```python
"""Microsoft Purview export adapter for RexLit metadata."""

import httpx
from azure.identity import DefaultAzureCredential
from pathlib import Path
from typing import Iterator
import json

class PurviewExportAdapter:
    """Export RexLit metadata to Microsoft Purview eDiscovery."""

    def __init__(self, tenant_id: str, case_id: str):
        self.tenant_id = tenant_id
        self.case_id = case_id
        self.credential = DefaultAzureCredential()
        self.graph_endpoint = "https://graph.microsoft.com/v1.0"

    def export_manifest(self, manifest_path: Path) -> None:
        """Upload RexLit manifest to Purview case as external data source."""

        token = self.credential.get_token(
            "https://graph.microsoft.com/.default"
        ).token

        # Read RexLit manifest (JSONL)
        with open(manifest_path) as f:
            for line in f:
                doc = json.loads(line)
                self._upload_document_metadata(token, doc)

    def _upload_document_metadata(self, token: str, doc: dict) -> None:
        """Upload single document metadata to Purview."""

        # Convert RexLit metadata to Purview format
        purview_doc = {
            "id": doc["sha256_hash"],
            "name": doc["filename"],
            "path": doc["path"],
            "size": doc["size"],
            "created": doc["created"],
            "modified": doc["modified"],
            "custodian": doc.get("custodian", "Unknown"),
            "docType": doc.get("doctype", "Unknown"),
            "source": "RexLit",
            "metadata": {
                "batesNumber": doc.get("bates_number"),
                "ocrConfidence": doc.get("ocr_confidence"),
                "privilegeClassification": doc.get("privilege_classification"),
                "sha256": doc["sha256_hash"],
            }
        }

        # Upload to Purview case
        with httpx.Client() as client:
            response = client.post(
                f"{self.graph_endpoint}/security/cases/ediscoveryCases/{self.case_id}/custodians/externalDataSources",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json=purview_doc,
                timeout=30.0
            )
            response.raise_for_status()
```

#### Step 2: Add CLI Command for Purview Export

`rexlit/cli.py`:

```python
@app.command()
def export_to_purview(
    manifest: Path = typer.Argument(..., help="RexLit manifest JSONL file"),
    tenant_id: str = typer.Option(..., help="Azure AD tenant ID"),
    case_id: str = typer.Option(..., help="Purview eDiscovery case ID"),
):
    """Export RexLit metadata to Microsoft Purview eDiscovery case.

    Example:
        rexlit export-to-purview ./out/manifest.jsonl \\
          --tenant-id abc123 \\
          --case-id 456def
    """
    from rexlit.app.adapters.purview_export_adapter import PurviewExportAdapter

    adapter = PurviewExportAdapter(tenant_id, case_id)
    adapter.export_manifest(manifest)

    typer.echo(f"✓ Exported {manifest} to Purview case {case_id}")
```

#### Step 3: Usage Workflow

```bash
# Step 1: Process documents with RexLit (offline)
rexlit ingest ./evidence --manifest out/manifest.jsonl
rexlit index build ./evidence
rexlit bates stamp ./evidence --prefix ABC --output ./stamped

# Step 2: Export metadata to Purview (online)
export REXLIT_ONLINE=1
rexlit export-to-purview out/manifest.jsonl \
  --tenant-id "your-tenant-id" \
  --case-id "purview-case-id"

# Step 3: Search in Purview portal (includes RexLit data)
# Navigate to Purview → eDiscovery → Case → Search
# Query: "custodian:anderson AND source:RexLit"
```

### Benefits

- ✅ **Unified eDiscovery** across on-prem and cloud data
- ✅ **Centralized audit trail** in Purview
- ✅ **Preserve RexLit metadata** (Bates numbers, privilege classifications)
- ✅ **Search across sources** (Microsoft 365 + RexLit) in one query
- ✅ **Maintain offline processing** (export is optional, post-processing step)

### Limitations

- ⚠️ **One-way sync** (changes in Purview don't sync back to RexLit)
- ⚠️ **No live holds** on RexLit data (static export)
- ⚠️ **File content not uploaded** (only metadata; files remain on-prem)
- ⚠️ **API rate limits** (Microsoft Graph throttling for large exports)

---

## 4. Approach C: Hybrid Processing Architecture

### Overview

Design a **hybrid eDiscovery workflow** where:
1. **Purview** handles Microsoft 365 collection, legal holds, and cloud collaboration
2. **RexLit** handles offline processing, Bates stamping, and final production
3. **Bidirectional sync** keeps both platforms aligned

This is the **most comprehensive integration** and delivers maximum value.

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│ Microsoft Purview (Cloud Layer)                              │
│  ┌────────────────────────────────────────────┐              │
│  │ Collection & Preservation                  │              │
│  │  ├─ Legal holds on Microsoft 365          │              │
│  │  ├─ Custodian data mapping                │              │
│  │  └─ Initial search and review             │              │
│  └────────────────────────────────────────────┘              │
│           ↓ Export (PST, native files, metadata)             │
└───────────┼──────────────────────────────────────────────────┘
            │
            ↓ Download to secure on-prem environment
            │
┌───────────┼──────────────────────────────────────────────────┐
│ RexLit (On-Premises Processing Layer)                        │
│  ┌────────────────────────────────────────────┐              │
│  │ Offline Processing                         │              │
│  │  ├─ Ingest Purview exports                │              │
│  │  ├─ Merge with local file sources         │              │
│  │  ├─ OCR scanned documents                 │              │
│  │  ├─ Privilege classification (LLM)        │              │
│  │  ├─ Bates stamping                        │              │
│  │  └─ DAT/Opticon load file generation      │              │
│  └────────────────────────────────────────────┘              │
│           ↓ Export results                                   │
│  ┌────────────────────────────────────────────┐              │
│  │ Purview Sync Adapter                       │              │
│  │  ├─ Upload Bates metadata                 │              │
│  │  ├─ Sync privilege classifications        │              │
│  │  └─ Merge audit trails                    │              │
│  └────────────────────────────────────────────┘              │
│           ↑ Sync back to Purview (optional)                  │
└───────────┼──────────────────────────────────────────────────┘
            │
            ↑ Upload stamped files to Purview review set
            │
┌───────────┼──────────────────────────────────────────────────┐
│ Microsoft Purview (Review & Export Layer)                    │
│  ┌────────────────────────────────────────────┐              │
│  │ Final Review & Production                  │              │
│  │  ├─ Review Bates-stamped documents        │              │
│  │  ├─ Privilege log from RexLit             │              │
│  │  └─ Export final production set           │              │
│  └────────────────────────────────────────────┘              │
└──────────────────────────────────────────────────────────────┘
```

### Workflow Stages

#### Stage 1: Collection (Purview Cloud)

```
PURVIEW PORTAL:
1. Create eDiscovery case
2. Add custodians (Exchange, Teams, OneDrive, SharePoint)
3. Place legal holds on custodian data sources
4. Run initial searches (e.g., "privileged OR confidential")
5. Add results to review set
6. Export review set to local environment
   → Download: PST files, native files, load file
```

#### Stage 2: Processing (RexLit On-Prem)

```bash
# Import Purview exports
rexlit ingest ./purview-export --manifest out/manifest.jsonl

# Merge with local sources (non-Microsoft 365 data)
rexlit ingest ./local-files --manifest out/manifest.jsonl --append

# Build unified index
rexlit index build ./combined-corpus

# OCR scanned documents
rexlit ocr run ./scans --output ./text

# Privilege classification
rexlit privilege classify ./combined-corpus --batch

# Apply Bates numbers
rexlit bates stamp ./combined-corpus --prefix PROD001 --output ./stamped

# Generate load files
rexlit produce create ./stamped --format dat --output ./production
```

#### Stage 3: Sync Back (Bidirectional)

```bash
# Export RexLit results to Purview
rexlit export-to-purview out/manifest.jsonl \
  --tenant-id "abc123" \
  --case-id "purview-case-456" \
  --include-bates \
  --include-privilege

# Upload stamped PDFs to Purview review set (via Azure Blob)
rexlit upload-to-purview ./stamped \
  --case-id "purview-case-456" \
  --review-set-id "review-set-789"
```

#### Stage 4: Final Review (Purview Cloud)

```
PURVIEW PORTAL:
1. Review Bates-stamped documents in review set
2. View privilege classifications from RexLit
3. Collaborate with team on tagging/redactions
4. Export final production set
```

### Implementation Components

#### Component 1: Purview Export Importer

`rexlit/app/adapters/purview_import_adapter.py`:

```python
"""Import Microsoft Purview exports into RexLit."""

from pathlib import Path
import pandas as pd
from rexlit.ingest.discover import discover_files

class PurviewImportAdapter:
    """Import Purview exports (PST, native files, load files)."""

    def import_purview_export(
        self, export_dir: Path, load_file: Path
    ) -> Iterator[DocumentRecord]:
        """Import Purview export directory.

        Args:
            export_dir: Directory containing native files from Purview export
            load_file: Purview load file (CSV/DAT format)

        Yields:
            DocumentRecord objects with Purview metadata preserved
        """
        # Read Purview load file
        df = pd.read_csv(load_file, delimiter="þ")  # Concordance delimiter

        # Map Purview fields to RexLit schema
        for _, row in df.iterrows():
            yield DocumentRecord(
                path=export_dir / row["NativeFilePath"],
                filename=row["FileName"],
                custodian=row["Custodian"],
                doctype=row["DocumentType"],
                created=row["CreatedDate"],
                modified=row["ModifiedDate"],
                metadata={
                    "purview_doc_id": row["DocID"],
                    "purview_case_id": row["CaseID"],
                    "purview_export_date": row["ExportDate"],
                }
            )
```

#### Component 2: Bates Metadata Sync

`rexlit/app/adapters/purview_bates_sync_adapter.py`:

```python
"""Sync RexLit Bates numbers back to Purview."""

class PurviewBatesSyncAdapter:
    """Upload Bates metadata to Purview case."""

    def sync_bates_numbers(
        self, manifest_path: Path, case_id: str
    ) -> None:
        """Upload Bates assignments to Purview as document metadata.

        This allows Purview to:
        - Search by Bates range (e.g., "ABC0000100..ABC0000200")
        - Display Bates numbers in review set
        - Export with Bates metadata in load files
        """
        token = self.credential.get_token(
            "https://graph.microsoft.com/.default"
        ).token

        with open(manifest_path) as f:
            for line in f:
                doc = json.loads(line)

                if "bates_number" in doc:
                    # Update document in Purview with Bates metadata
                    self._update_purview_document(
                        token,
                        case_id,
                        doc["sha256_hash"],
                        {"batesNumber": doc["bates_number"]}
                    )
```

### Benefits

- ✅ **Best of both worlds**: Cloud scale + offline processing
- ✅ **Complete workflow coverage**: Collection → Processing → Review → Production
- ✅ **Fills Purview gaps**: Adds Bates stamping, offline mode, deterministic processing
- ✅ **Preserves Purview strengths**: Legal holds, collaboration, Microsoft 365 integration
- ✅ **Unified audit trail**: Merge RexLit and Purview logs
- ✅ **Cost optimization**: Offload processing to on-prem RexLit

### Challenges

- ⚠️ **Complexity**: Requires coordination between cloud and on-prem systems
- ⚠️ **Data transfer**: Large exports/uploads between Purview and RexLit
- ⚠️ **Synchronization**: Keep Purview and RexLit metadata aligned
- ⚠️ **Training**: Teams need to learn both platforms

---

## 5. Approach D: Feature-Specific Integrations

Rather than full platform integration, add **specific RexLit features** to Purview workflows as standalone modules.

### D1: Bates Stamping Service for Purview

**Problem:** Purview lacks Bates stamping capability.

**Solution:** Deploy RexLit as a **Bates stamping microservice** that Purview exports can call.

#### Architecture

```
Purview Export → Azure Function (RexLit Bates API) → Stamped PDFs → Upload to Purview
```

#### Implementation

```python
# Azure Function: bates_stamping_function.py

from azure.functions import HttpRequest, HttpResponse
from rexlit.pdf.bates import BatesStamper
import tempfile

def main(req: HttpRequest) -> HttpResponse:
    """Azure Function that stamps Bates numbers on PDFs."""

    # Get parameters from Purview
    pdf_bytes = req.get_body()
    bates_prefix = req.params.get("prefix", "PROD")
    bates_start = int(req.params.get("start", "1"))

    # Write to temp file
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(pdf_bytes)
        tmp.flush()

        # Stamp with RexLit
        stamper = BatesStamper(prefix=bates_prefix, start=bates_start)
        output_path = stamper.stamp(tmp.name)

        # Return stamped PDF
        with open(output_path, "rb") as f:
            return HttpResponse(
                f.read(),
                mimetype="application/pdf",
                headers={
                    "Content-Disposition": "attachment; filename=stamped.pdf",
                    "X-Bates-Number": stamper.get_last_bates()
                }
            )
```

#### Usage from Purview

```powershell
# PowerShell script to stamp Purview exports

$exports = Get-ChildItem -Path "./purview-export/*.pdf"
$batesNumber = 1

foreach ($pdf in $exports) {
    $response = Invoke-RestMethod `
        -Uri "https://rexlit-bates.azurewebsites.net/api/stamp" `
        -Method POST `
        -InFile $pdf.FullName `
        -Headers @{
            "x-functions-key" = $env:AZURE_FUNCTION_KEY
        } `
        -Body @{
            prefix = "PROD001"
            start = $batesNumber
        }

    $response | Out-File "./stamped/$($pdf.Name)"
    $batesNumber = $response.Headers["X-Bates-Number"]
}
```

### D2: Offline Processing Mode for Purview

**Problem:** Purview requires constant internet connectivity.

**Solution:** Use RexLit as **offline cache** for Purview data.

#### Workflow

```
1. [Online] Purview: Export case data to local environment
2. [Offline] RexLit: Index and search exported data
3. [Offline] RexLit: Perform privilege review, tagging
4. [Online] Purview: Sync results back when network available
```

### D3: LLM-Powered Privilege Classification for Purview

**Problem:** Purview has generic Security Copilot, not privilege-specific LLMs.

**Solution:** Deploy RexLit's privilege service as **Azure Container Instance** that Purview can call.

#### API Endpoint

```python
# Azure Container Instance: rexlit-privilege-api

from fastapi import FastAPI
from rexlit.app.privilege_service import PrivilegeService

app = FastAPI()

@app.post("/classify")
async def classify_document(request: ClassifyRequest):
    """Classify document for privilege (called by Purview)."""

    service = PrivilegeService(
        privilege_port=GroqPrivilegeAdapter(),
        ledger=PurviewAuditAdapter()
    )

    decision = await service.classify_document(
        doc_path=request.doc_id,
        content=request.content
    )

    return {
        "classification": decision.classification,
        "confidence": decision.confidence,
        "rationale": decision.rationale,
        "edrm_code": decision.edrm_code
    }
```

---

## 6. Technical Implementation Details

### Required Azure/Microsoft Services

| Service | Purpose | Cost Estimate |
|---------|---------|---------------|
| **Azure AD (Entra ID)** | App registration, authentication | Included with M365 |
| **Microsoft Graph API** | Purview data access | Included with M365 |
| **Azure Functions** | Bates stamping microservice | ~$0.20 per 1M executions |
| **Azure Container Instances** | Privilege classification API | ~$0.0000125/second |
| **Azure Blob Storage** | File staging for exports/imports | ~$0.02/GB/month |

### Authentication Flow

```
RexLit → Azure AD (OAuth 2.0) → Access Token → Microsoft Graph API → Purview
```

#### Example: Get Access Token

```python
from azure.identity import DefaultAzureCredential

# Use managed identity (in Azure) or Azure CLI (local dev)
credential = DefaultAzureCredential()

# Get token for Microsoft Graph
token = credential.get_token("https://graph.microsoft.com/.default")

# Use token in API calls
headers = {"Authorization": f"Bearer {token.token}"}
```

### Microsoft Graph API Endpoints for Purview

| Operation | Endpoint | Method |
|-----------|----------|--------|
| **List eDiscovery cases** | `/security/cases/ediscoveryCases` | GET |
| **Get case details** | `/security/cases/ediscoveryCases/{id}` | GET |
| **Add external data source** | `/security/cases/ediscoveryCases/{id}/custodians/externalDataSources` | POST |
| **Log AI interaction** | `/security/purview/aiInteractions` | POST |
| **Get audit logs** | `/security/auditLogs` | GET |

---

## 7. Microsoft Graph API Integration

### Full Example: Export RexLit Manifest to Purview

```python
"""Complete example of RexLit-to-Purview export."""

import json
from pathlib import Path
import httpx
from azure.identity import DefaultAzureCredential

def export_rexlit_to_purview(
    manifest_path: Path,
    tenant_id: str,
    case_id: str
):
    """Export RexLit manifest to Purview eDiscovery case."""

    # Authenticate
    credential = DefaultAzureCredential()
    token = credential.get_token("https://graph.microsoft.com/.default")

    # Read RexLit manifest
    documents = []
    with open(manifest_path) as f:
        for line in f:
            documents.append(json.loads(line))

    # Upload each document
    with httpx.Client() as client:
        for doc in documents:
            # Convert RexLit schema to Purview schema
            purview_doc = {
                "displayName": doc["filename"],
                "email": f"{doc.get('custodian', 'unknown')}@contoso.com",
                "createdDateTime": doc["created"],
                "additionalData": {
                    "sha256": doc["sha256_hash"],
                    "batesNumber": doc.get("bates_number"),
                    "privilegeClassification": doc.get("privilege_classification"),
                    "source": "RexLit"
                }
            }

            # POST to Purview
            response = client.post(
                f"https://graph.microsoft.com/v1.0/security/cases/ediscoveryCases/{case_id}/custodians",
                headers={
                    "Authorization": f"Bearer {token.token}",
                    "Content-Type": "application/json"
                },
                json=purview_doc,
                timeout=60.0
            )

            if response.status_code != 201:
                print(f"Failed to upload {doc['filename']}: {response.text}")
            else:
                print(f"✓ Uploaded {doc['filename']}")

# Usage
export_rexlit_to_purview(
    manifest_path=Path("./out/manifest.jsonl"),
    tenant_id="your-tenant-id",
    case_id="purview-case-id"
)
```

---

## 8. DSPM for AI Configuration for RexLit

### Complete PowerShell Setup Script

```powershell
# Configure Microsoft Purview DSPM for AI to monitor RexLit privilege classification

# Prerequisites:
# 1. Install PowerShell 7+
# 2. Install ExchangeOnlineManagement module
# 3. Connect to Security & Compliance PowerShell

# Connect to Purview
Connect-IPPSSession -UserPrincipalName admin@contoso.com

# Enable Microsoft Purview Audit
Set-AdminAuditLogConfig -UnifiedAuditLogIngestionEnabled $true

# Create KYD policy for RexLit privilege classification
New-FeatureConfiguration `
  -FeatureScenario KnowYourData `
  -Name "DSPM for AI - RexLit Privilege Classification" `
  -Mode Enable `
  -ScenarioConfig '{
    "Activities": ["UploadText", "DownloadText"],
    "EnforcementPlanes": ["Entra"],
    "SensitiveTypeIds": ["All"],
    "IsIngestionEnabled": true
  }' `
  -Locations '[{
    "Workload": "Applications",
    "Location": "rexlit-privilege-app-id",
    "LocationSource": "Entra",
    "LocationType": "Application",
    "Inclusions": [{
      "Type": "Application",
      "Identity": "rexlit-privilege-app-id"
    }]
  }]'

# Create Communication Compliance policy
New-CommunicationCompliancePolicy `
  -Name "DSPM for AI - RexLit Unethical Behavior Detection" `
  -Description "Monitor RexLit privilege prompts for inappropriate content" `
  -SupervisoryReviewPolicy $true `
  -RecordTypePolicy "AIInteractions" `
  -Conditions @{
    ApplicationId = "rexlit-privilege-app-id"
    SensitiveInformationTypes = @("All")
  }

# Create Insider Risk Management policy
New-InsiderRiskPolicy `
  -Name "DSPM for AI - RexLit Risky Privilege Usage" `
  -Description "Detect risky prompts in RexLit privilege classification" `
  -PolicyTemplate "RiskyAIUsage" `
  -Users "All" `
  -IndicatorSettings @{
    AIInteractionIndicators = $true
    ApplicationId = "rexlit-privilege-app-id"
  }

# Validate configuration
Write-Host "✓ DSPM for AI configured for RexLit"
Write-Host "  - Audit: Enabled"
Write-Host "  - KYD Policy: DSPM for AI - RexLit Privilege Classification"
Write-Host "  - Communication Compliance: DSPM for AI - RexLit Unethical Behavior Detection"
Write-Host "  - Insider Risk: DSPM for AI - RexLit Risky Privilege Usage"
```

### Validation Steps

```powershell
# Check audit status
Get-AdminAuditLogConfig | Select-Object UnifiedAuditLogIngestionEnabled

# List KYD policies
Get-FeatureConfiguration -FeatureScenario KnowYourData

# Check Communication Compliance policies
Get-CommunicationCompliancePolicy | Where-Object { $_.Name -like "*RexLit*" }

# Check Insider Risk policies
Get-InsiderRiskPolicy | Where-Object { $_.Name -like "*RexLit*" }
```

---

## 9. Security and Compliance Considerations

### Data Privacy

**Challenge:** RexLit is designed for offline-first, privacy-preserving workflows. Purview integration requires uploading data to Microsoft's cloud.

**Mitigation Strategies:**
1. **Selective sync**: Only upload metadata, not full document content
2. **Hash-based references**: Use SHA-256 hashes to reference documents without uploading files
3. **Encryption in transit**: All API calls use TLS 1.3
4. **Privacy-preserving audit**: Continue hashing chain-of-thought reasoning before Purview upload
5. **Opt-in model**: Purview integration disabled by default (`REXLIT_PURVIEW_INTEGRATION=0`)

### Access Control

**RexLit Side:**
- File system permissions (UNIX ACLs)
- Environment variable for Purview credentials (`REXLIT_PURVIEW_CLIENT_SECRET`)
- Audit log of all Purview API calls

**Purview Side:**
- Azure AD RBAC (eDiscovery Manager, Administrator roles)
- Case-based permissions
- Conditional access policies (MFA, device compliance)

### Audit Trail Integrity

**Challenge:** RexLit's SHA-256 hash chain guarantees audit trail integrity. Purview's cloud logs are trust-based.

**Solution:**
- **Dual audit trails**: Maintain both RexLit local hash chain AND Purview cloud logs
- **Cross-validation**: Periodic verification that Purview logs match RexLit local logs
- **Conflict resolution**: RexLit local logs are authoritative in case of discrepancies

### Compliance Certifications

| Standard | RexLit (Local) | Purview (Cloud) | Hybrid Approach |
|----------|----------------|-----------------|-----------------|
| **SOC 2** | User-managed | Microsoft-certified | Depends on deployment |
| **ISO 27001** | User-managed | Microsoft-certified | Depends on deployment |
| **GDPR** | User-controlled | Microsoft DPA | Combined compliance |
| **HIPAA** | User-managed | Microsoft BAA | Combined compliance |
| **FedRAMP** | User-managed | Purview FedRAMP High | Depends on deployment |

---

## 10. Cost-Benefit Analysis

### Integration Costs

| Component | Setup Cost | Ongoing Cost (Annual) |
|-----------|------------|----------------------|
| **Azure AD app registration** | $0 (one-time) | $0 |
| **Microsoft Graph API calls** | $0 | $0 (included in M365) |
| **Azure Functions (Bates stamping)** | $0 | ~$50-$200 (low volume) |
| **Azure Container Instances (Privilege API)** | $0 | ~$100-$500 (on-demand) |
| **Developer time (integration code)** | ~40-80 hours | ~10-20 hours (maintenance) |

**Total Estimated Cost:** $150-$700/year (excluding developer time)

### Value Delivered

| Capability Added | Business Value | Cost Savings |
|------------------|----------------|--------------|
| **Bates stamping in Purview** | High (fills critical gap) | ~$2,000-$5,000/year (third-party tool licenses) |
| **Offline processing** | Medium-High (air-gapped workflows) | Priceless (enables cases that were impossible) |
| **LLM privilege classification** | High (accuracy + speed) | ~$10,000-$50,000/year (attorney time savings) |
| **Deterministic processing** | Medium (legal defensibility) | Risk mitigation (invaluable) |
| **Unified audit trail** | Medium (compliance) | ~$5,000-$10,000/year (audit preparation) |

**Total Estimated Value:** $17,000-$65,000/year + risk mitigation

**ROI:** 20-100x (value delivered vs. integration cost)

---

## 11. Implementation Roadmap

### Phase 1: Proof of Concept (4-6 weeks)

**Goal:** Validate core integration patterns with minimal investment.

**Deliverables:**
- ✅ Azure AD app registration for RexLit
- ✅ Basic Microsoft Graph API authentication
- ✅ Single-document export from RexLit to Purview
- ✅ DSPM for AI KYD policy for privilege classification

**Success Criteria:**
- RexLit can authenticate with Azure AD
- One document successfully uploaded to Purview case
- Privilege classification logged in DSPM for AI

### Phase 2: Bates Stamping Integration (6-8 weeks)

**Goal:** Add Bates stamping capability to Purview workflows.

**Deliverables:**
- ✅ Azure Function for Bates stamping API
- ✅ PowerShell script for Purview export stamping
- ✅ Upload stamped PDFs back to Purview review set
- ✅ Bates metadata sync to Purview

**Success Criteria:**
- Purview exports can be Bates-stamped via RexLit API
- Stamped PDFs visible in Purview review set with Bates metadata

### Phase 3: Hybrid Workflow (12-16 weeks)

**Goal:** Full bidirectional sync between RexLit and Purview.

**Deliverables:**
- ✅ Purview import adapter (read Purview exports)
- ✅ Purview export adapter (write RexLit results to Purview)
- ✅ Privilege classification sync
- ✅ Unified audit trail (merge RexLit + Purview logs)
- ✅ CLI commands: `rexlit import-from-purview`, `rexlit export-to-purview`

**Success Criteria:**
- Complete case workflow: Purview collection → RexLit processing → Purview review
- Bates numbers, privilege classifications, and audit logs synchronized
- Documentation and training materials complete

### Phase 4: Production Hardening (8-12 weeks)

**Goal:** Enterprise-grade reliability, security, and compliance.

**Deliverables:**
- ✅ Error handling and retry logic
- ✅ Rate limiting and throttling (Microsoft Graph API)
- ✅ Comprehensive logging and monitoring
- ✅ Security review (penetration testing)
- ✅ Compliance validation (SOC 2, GDPR)
- ✅ User documentation and training

**Success Criteria:**
- 99.9% uptime for integration services
- Security audit passed
- 5+ successful production cases completed

---

## 12. Use Cases and Examples

### Use Case 1: Small Law Firm with Mixed Data Sources

**Scenario:**
- 50-attorney firm with Microsoft 365 E3 licenses (not E5)
- Case involves Microsoft 365 emails + local paper scans + PST exports
- Budget: $10K for eDiscovery tools (cannot afford Purview Premium)

**Solution: RexLit as Primary + Purview Standard for Holds**

```
1. Purview Standard: Place legal holds on Microsoft 365 mailboxes (included in E3)
2. Purview Standard: Export mailboxes to PST
3. RexLit: Import PST + scanned docs + local files
4. RexLit: OCR, privilege review, Bates stamping, load file generation
5. RexLit: Generate production set (DAT format)
6. [Optional] RexLit: Export metadata back to Purview for final review
```

**Cost:** $0 (Purview Standard included, RexLit open-source)
**Time Saved:** ~40 hours (vs. manual review + third-party Bates tool)

### Use Case 2: Enterprise with Air-Gapped Review Room

**Scenario:**
- Large corporation with Purview Premium (E5 licenses)
- Highly sensitive case requiring offline review (no internet in review room)
- Need to maintain Purview collaboration for distributed team

**Solution: Hybrid Architecture**

```
1. Purview: Collect and hold Microsoft 365 data (1M+ documents)
2. Purview: Initial culling and keyword searches (reduce to 100K relevant docs)
3. Purview: Export 100K documents to encrypted USB drive
4. RexLit (Air-Gapped Room): Import, index, privilege review (offline)
5. RexLit (Air-Gapped Room): Bates stamping and redaction
6. [Network Available] RexLit: Sync results back to Purview
7. Purview: Final team review and export
```

**Cost:** $0 additional (leverage existing Purview Premium)
**Benefit:** Enables previously impossible air-gapped workflows

### Use Case 3: Government Agency with FedRAMP Requirements

**Scenario:**
- Federal agency with FedRAMP High compliance requirement
- Purview deployed in Azure Government Cloud (FedRAMP High certified)
- Need Bates stamping (not available in Purview)

**Solution: RexLit Bates Stamping Azure Function**

```
1. Purview (Azure Gov): Collect and review documents
2. Purview (Azure Gov): Export production set
3. Azure Function (Azure Gov): Call RexLit Bates API (deployed in FedRAMP boundary)
4. Azure Function (Azure Gov): Upload stamped PDFs back to Purview
5. Purview (Azure Gov): Final export with Bates numbers
```

**Cost:** ~$200/year (Azure Functions in Azure Gov)
**Benefit:** Maintain FedRAMP compliance while adding Bates capability

### Use Case 4: Solo Practitioner Upgrading to Purview

**Scenario:**
- Solo practitioner currently using RexLit (open-source, $0 cost)
- Joins firm with Microsoft 365 E5 (gains Purview access)
- Wants to leverage Purview collaboration but keep RexLit skills

**Solution: RexLit as Offline Extension of Purview**

```
1. Purview: Use for Microsoft 365 data collection (new capability)
2. Purview: Export to local environment
3. RexLit: Continue using familiar CLI for processing
4. RexLit: Export results back to Purview for firm collaboration
```

**Cost:** $0 incremental (Purview included in firm's E5, RexLit open-source)
**Benefit:** Smooth transition, preserve existing workflows

---

## 13. Conclusion and Recommendations

### Primary Recommendation

**Implement Approach C (Hybrid Architecture) with selective use of Approach A (DSPM for AI monitoring).**

**Rationale:**
1. **Fills critical gaps**: Adds Bates stamping, offline processing, deterministic workflows to Purview
2. **Preserves strengths**: Maintains Purview's legal holds, collaboration, Microsoft 365 integration
3. **Maximum ROI**: Estimated 20-100x return on integration investment
4. **Flexible deployment**: Works for small firms (RexLit-primary) and enterprises (Purview-primary)
5. **Compliance-friendly**: Supports air-gapped workflows while enabling cloud collaboration

### Implementation Priority

**Phase 1 (Highest Priority):** Bates Stamping Integration
**Why:** Fills the most critical gap in Purview (no Bates stamping), high demand, relatively simple implementation.

**Phase 2 (High Priority):** Hybrid Workflow
**Why:** Unlocks air-gapped use cases, enables mixed-source productions, delivers maximum value.

**Phase 3 (Medium Priority):** DSPM for AI Monitoring
**Why:** Valuable for compliance oversight, but not critical for core workflows.

**Phase 4 (Low Priority):** Feature-Specific Microservices
**Why:** Nice-to-have enhancements, but hybrid architecture covers most needs.

### Success Metrics

Track these KPIs to measure integration success:

| Metric | Baseline (RexLit or Purview Alone) | Target (Hybrid) |
|--------|-----------------------------------|-----------------|
| **Cases using Bates stamping** | 0% (Purview) | 80%+ |
| **Offline review capability** | 0% (Purview) | 100% |
| **Cost per document processed** | $0.50-$2.00 (Purview only) | $0.10-$0.50 (hybrid) |
| **Privilege review accuracy** | 70-80% (manual) | 90%+ (RexLit LLM) |
| **Audit trail verification time** | 4-8 hours (manual) | <1 hour (automated) |

---

## 14. Next Steps

### For Microsoft Purview Product Team

If Microsoft is interested in formally integrating RexLit capabilities:

1. **Evaluate RexLit codebase** for integration into Purview
2. **Consider licensing RexLit** as a Purview module (commercial open-source)
3. **Add Bates stamping** to Purview Premium tier (fill critical gap)
4. **Develop offline mode** for Purview (air-gapped scenarios)
5. **Enhance privilege classification** with dedicated LLM models (vs. generic Copilot)

### For RexLit Development Team

To prepare for Purview integration:

1. **Implement Microsoft Graph API adapters** (priority: export, Bates sync)
2. **Create Azure deployment templates** (Functions, Container Instances)
3. **Document Purview integration** (user guides, API docs)
4. **Build reference implementations** (sample hybrid workflows)
5. **Engage Microsoft Purview team** (partnership discussions)

### For Organizations Considering Integration

1. **Start with Phase 1 POC** (4-6 weeks, minimal cost)
2. **Validate use cases** (air-gapped review, Bates stamping, mixed sources)
3. **Pilot with small case** (100-1,000 documents)
4. **Measure ROI** (time saved, cost reduction, new capabilities)
5. **Scale to production** (Phases 2-4, 6-12 months)

---

## Appendix A: Microsoft Graph API Permissions Reference

### Required API Permissions for RexLit Integration

| Permission | Type | Purpose | Justification |
|------------|------|---------|---------------|
| `eDiscovery.Read.All` | Application | Read eDiscovery cases | List cases, read case metadata |
| `eDiscovery.ReadWrite.All` | Application | Write eDiscovery data | Upload RexLit results to Purview |
| `InformationProtection.Read.All` | Delegated | Read sensitivity labels | Detect sensitive data in privilege review |
| `AuditLog.ReadWrite.All` | Application | Write audit logs | Log RexLit operations to Purview audit |
| `Files.ReadWrite.All` | Application | Access SharePoint/OneDrive | Upload stamped PDFs to Purview review sets |

### Consent and Admin Approval

```bash
# Grant admin consent for RexLit app
az ad app permission admin-consent --id <rexlit-app-id>
```

---

## Appendix B: Sample Integration Code

### Complete Example: RexLit → Purview Bates Sync

```python
#!/usr/bin/env python3
"""
Complete example: Sync RexLit Bates numbers to Microsoft Purview.

Usage:
    python sync_bates_to_purview.py \\
        --manifest ./out/manifest.jsonl \\
        --tenant-id abc123 \\
        --case-id purview-case-456
"""

import json
import argparse
from pathlib import Path
import httpx
from azure.identity import DefaultAzureCredential

def sync_bates_to_purview(
    manifest_path: Path,
    tenant_id: str,
    case_id: str,
):
    """Sync Bates numbers from RexLit manifest to Purview case."""

    # Authenticate with Azure AD
    credential = DefaultAzureCredential()
    token = credential.get_token("https://graph.microsoft.com/.default")

    # Read RexLit manifest
    print(f"Reading manifest: {manifest_path}")
    documents = []
    with open(manifest_path) as f:
        for line in f:
            doc = json.loads(line)
            if "bates_number" in doc:
                documents.append(doc)

    print(f"Found {len(documents)} documents with Bates numbers")

    # Upload to Purview
    base_url = "https://graph.microsoft.com/v1.0"
    headers = {
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "application/json"
    }

    success_count = 0
    with httpx.Client(timeout=60.0) as client:
        for doc in documents:
            # Prepare Purview metadata
            payload = {
                "id": doc["sha256_hash"],
                "additionalData": {
                    "batesNumber": doc["bates_number"],
                    "source": "RexLit",
                    "syncTimestamp": "2025-11-20T12:00:00Z"
                }
            }

            # PATCH document in Purview case
            response = client.patch(
                f"{base_url}/security/cases/ediscoveryCases/{case_id}/custodians/{doc['sha256_hash']}",
                headers=headers,
                json=payload
            )

            if response.status_code in (200, 204):
                print(f"✓ Synced {doc['filename']}: {doc['bates_number']}")
                success_count += 1
            else:
                print(f"✗ Failed {doc['filename']}: {response.status_code} {response.text}")

    print(f"\nSync complete: {success_count}/{len(documents)} documents")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--case-id", required=True)
    args = parser.parse_args()

    sync_bates_to_purview(args.manifest, args.tenant_id, args.case_id)
```

---

**Document Version:** 1.0
**Maintained by:** RexLit + Microsoft Purview Integration Working Group
**Feedback:** Submit issues to [repository link]
