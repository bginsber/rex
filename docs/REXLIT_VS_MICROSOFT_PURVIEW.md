# RexLit vs. Microsoft Purview eDiscovery: A Comparative Analysis

**Last Updated:** 2025-11-20
**RexLit Version:** v0.2.0-m1
**Microsoft Purview:** Current as of 2025

## Executive Summary

RexLit and Microsoft Purview eDiscovery are both electronic discovery platforms designed to identify, review, and manage electronically stored information (ESI) for legal cases and investigations. However, they represent fundamentally different approaches to eDiscovery:

- **Microsoft Purview**: Cloud-first, enterprise-scale platform deeply integrated with Microsoft 365 ecosystem
- **RexLit**: Offline-first, open-source UNIX toolkit designed for air-gapped environments and small-to-medium practices

This document provides a detailed comparison to help legal teams, IT professionals, and solo practitioners understand which solution best fits their needs.

---

## Quick Comparison Matrix

| Dimension | RexLit | Microsoft Purview eDiscovery |
|-----------|--------|------------------------------|
| **Deployment** | Local/on-premises CLI + optional web UI | Cloud-only (Microsoft 365/Azure) |
| **Network Requirements** | Offline-first (optional online features) | Requires constant internet connectivity |
| **Data Sources** | Any file system (PDFs, DOCX, emails, TXT) | Microsoft 365 services only (Exchange, Teams, OneDrive, SharePoint) |
| **Pricing Model** | Open-source (TBD license) | Enterprise subscription (E5/A5 licenses ~$57/user/month) |
| **Target Users** | Solo practitioners, small firms, air-gapped review rooms | Enterprise legal departments with Microsoft 365 infrastructure |
| **Processing Model** | Deterministic, reproducible, locally controlled | Cloud-based, dynamic, Microsoft-managed |
| **Audit Trail** | Tamper-evident SHA-256 hash chain in local JSONL | Cloud-based audit logs in Microsoft ecosystem |
| **Data Sovereignty** | Complete local control | Data stored in Microsoft's cloud infrastructure |
| **Extensibility** | Open-source, modular architecture | Closed platform with Microsoft integrations |

---

## 1. Deployment & Architecture

### Microsoft Purview eDiscovery
- **Cloud-native**: Runs entirely in Microsoft 365/Azure cloud
- **Portal-based**: Web interface accessed through Microsoft Purview portal
- **Integrated**: Deep hooks into Exchange Online, Teams, SharePoint, OneDrive
- **Infrastructure**: Microsoft-managed servers, storage, and compute
- **Access**: Requires Microsoft 365 E5 license or eDiscovery add-ons
- **Scalability**: Elastic cloud scaling for enterprise workloads

### RexLit
- **Local-first**: CLI tool runs on Linux/macOS/Windows (via WSL)
- **Self-hosted**: All processing happens on practitioner's hardware
- **Modular**: Ports/adapters architecture with pluggable components
- **Storage**: Local file system + Tantivy search index
- **Access**: Open-source installation via PyPI or source
- **Scalability**: Limited by local hardware (tested to 100K documents)

**When RexLit is better:**
- Air-gapped environments (government, defense, high-security cases)
- Firms without Microsoft 365 infrastructure
- Solo practitioners with cost constraints
- Cases requiring data sovereignty or offline processing
- Organizations requiring reproducible, deterministic workflows

**When Purview is better:**
- Organizations already invested in Microsoft 365
- Large enterprises with distributed teams
- Cases requiring real-time collaboration across time zones
- Teams needing integrated hold/preservation of live Microsoft 365 data
- Organizations with dedicated IT staff for cloud management

---

## 2. Data Sources & Collection

### Microsoft Purview eDiscovery

**Supported Sources:**
- Exchange Online (emails, calendars)
- Microsoft Teams (chats, channels, files)
- OneDrive for Business
- SharePoint Online
- Microsoft 365 Groups
- Viva Engage (formerly Yammer)

**Collection Features:**
- Direct API access to Microsoft services
- Real-time legal holds on mailboxes and sites
- Cloud attachments and SharePoint versions
- Automatic custodian mapping across services
- Advanced indexing (automatic reindexing of partially indexed content)

**Limitations:**
- **Cannot process non-Microsoft data** (local files, PST exports, paper scans)
- **Requires active Microsoft 365 subscriptions** for all custodians
- **No support for third-party email** (Gmail exports, legacy systems)

### RexLit

**Supported Sources:**
- Local file systems (any directory structure)
- PDF documents (native and scanned)
- Microsoft Word documents (DOCX)
- Email files (EML, MSG via future adapters)
- Plain text and Markdown files
- Any file type with text extraction adapters

**Collection Features:**
- Streaming ingest with O(1) memory profile
- Secure path resolution with symlink validation
- Deterministic processing (SHA-256 sorted)
- Root-bound security (13 path traversal tests)
- OCR for scanned documents (Tesseract)
- Custodian and document type tagging

**Limitations:**
- **No direct cloud API access** (requires manual export from cloud services)
- **Cannot place legal holds** on live data sources
- **Smaller scale** (tested to 100K documents vs. millions in Purview)

**When RexLit is better:**
- Processing physical documents (scanned files)
- Mixed-source productions (Microsoft + Google + local files)
- PST/OST exports from legacy Exchange servers
- Cases involving non-Microsoft enterprise systems
- Offline review scenarios (courtroom, client sites)

**When Purview is better:**
- All data already in Microsoft 365
- Need to preserve data in place (legal holds)
- Real-time monitoring of communications
- Large-scale custodian data mapping

---

## 3. Search & Analytics

### Microsoft Purview eDiscovery

**Search Capabilities:**
- Keyword Query Language (KeyQL) with advanced operators
- Filters by date, custodian, content type, sensitivity labels
- Search statistics and sampling
- AI-powered relevance predictions (premium tier)
- Microsoft Security Copilot integration (natural language queries)

**Analytics (Premium tier only):**
- Near-duplicate detection (textual similarity)
- Email threading (conversation reconstruction)
- Themes analysis (ML-based topic modeling)
- Optical character recognition (images)
- Predictive coding models
- Advanced indexing with automatic reprocessing

**Review Sets:**
- Cloud-based review sets in Azure Storage
- Collaborative tagging and annotations
- Export to third-party review platforms (Relativity, etc.)

### RexLit

**Search Capabilities:**
- Tantivy full-text search (BM25 ranking)
- Boolean query syntax (AND, OR, NOT, phrase queries)
- Dense/hybrid search with Kanon 2 embeddings (online mode)
- Metadata filters (custodian, doctype, date ranges)
- O(1) metadata cache for instant lookups
- Search statistics and result previewing

**Analytics (Current/Planned):**
- ✅ OCR with Tesseract (confidence scoring)
- ✅ Privilege classification (pattern + LLM escalation)
- ✅ Deduplication analysis
- ✅ Impact discovery reports (Sedona Conference-aligned)
- 🚧 Email threading (planned for M2)
- 🚧 Redaction planning with PII detection (planned for M2)
- 🚧 Custodian communication graphs (planned for M2)

**Review Sets:**
- Local file system organization
- Optional web UI for document review (experimental)
- Hash-based document access for security
- Privilege decision recording with audit trail

**When RexLit is better:**
- Small-to-medium document sets (<100K documents)
- Cases requiring explainable, deterministic ranking
- Offline review workflows
- Cost-sensitive projects (no per-document fees)
- Custom analytics via Python extensibility

**When Purview is better:**
- Massive document sets (millions of items)
- Teams requiring collaborative review
- Complex AI-driven analytics (predictive coding, themes)
- Natural language queries via Security Copilot
- Integration with Microsoft compliance ecosystem

---

## 4. Production & Export

### Microsoft Purview eDiscovery

**Export Capabilities:**
- Native file exports (original formats)
- PST exports for email
- PDF exports with annotations
- Load file generation (DAT/Concordance-compatible)
- Unified export structure (standardized across premium/standard)
- Detailed export reports

**Production Features:**
- Redaction support (premium tier)
- Export to third-party platforms (Relativity, etc.)
- Cloud-based export staging
- Role-based export permissions

**Limitations:**
- **No Bates stamping** (requires third-party tools)
- **No native load file customization** (fixed formats)
- **Cloud dependency** (exports must download from Azure)

### RexLit

**Export Capabilities:**
- DAT load files (delimited text with metadata)
- Opticon format (image-based productions)
- Bates stamping with layout-aware placement
- Deterministic Bates sequencing (SHA-256 sorted)
- Audit-ready production manifests
- Full provenance tracking

**Production Features:**
- ✅ Bates number prefixes and zero-padding
- ✅ Position presets (bottom-right, top-right, etc.)
- ✅ Rotation-aware stamping (handles landscape pages)
- ✅ Safe-area detection (0.5" margins)
- ✅ Font size and color customization
- 🚧 Redaction planning (M2 feature)

**When RexLit is better:**
- Cases requiring Bates stamping
- Small firms without enterprise review platforms
- Productions requiring deterministic, reproducible numbering
- Offline production workflows
- Custom load file formats via Python

**When Purview is better:**
- Large-scale exports to enterprise platforms
- Cloud-based staging for distributed teams
- Integration with Microsoft compliance workflows
- Exports requiring Microsoft-specific metadata

---

## 5. Compliance & Audit

### Microsoft Purview eDiscovery

**Audit Features:**
- Cloud-based audit logs in Microsoft ecosystem
- Process tracking (searches, exports, holds)
- Role-based access control (RBAC)
- Compliance manager integration
- Audit log retention policies
- Export audit reports

**Compliance:**
- SOC 2, ISO 27001 certified infrastructure
- GDPR compliance (Microsoft-managed)
- Data residency options (regional data centers)
- Encryption at rest and in transit (Microsoft-managed)

**Limitations:**
- **Audit logs stored in Microsoft cloud** (not locally verifiable)
- **No hash-chain verification** (trust-based audit trail)
- **Dependent on Microsoft's compliance certifications**

### RexLit

**Audit Features:**
- Tamper-evident SHA-256 hash chain
- Append-only JSONL ledger with fsync durability
- Local audit verification (`rexlit audit verify`)
- Full operation provenance (ingest, index, OCR, Bates, privilege)
- Privacy-preserving audit (hashed chain-of-thought for LLM reasoning)
- Deterministic processing for reproducibility

**Compliance:**
- EDRM privilege log protocol compliance
- Sedona Conference proportionality alignment
- Texas/Florida civil procedure rules engine
- Methods appendix generation (defensible methodology)
- Complete local control of audit trail

**When RexLit is better:**
- Cases requiring locally verifiable audit trails
- Air-gapped environments without cloud trust
- Small practices needing simple audit compliance
- Jurisdictions with data sovereignty requirements
- Cases requiring deterministic, reproducible processing

**When Purview is better:**
- Enterprises requiring SOC 2/ISO 27001 compliance
- Multi-jurisdictional cases with regional data residency
- Organizations with dedicated compliance teams
- Cases requiring Microsoft's compliance certifications

---

## 6. Security & Access Control

### Microsoft Purview eDiscovery

**Security Features:**
- Enterprise RBAC (eDiscovery Manager, Administrator roles)
- Multi-factor authentication (Azure AD)
- Conditional access policies
- Data loss prevention (DLP) integration
- Sensitivity label enforcement
- Microsoft Defender integration

**Access Control:**
- Case-based permissions
- Custodian access restrictions
- Export controls
- Audit trail of all access

**Threat Model:**
- Trust in Microsoft's cloud security
- Network-based attacks (phishing, credential theft)
- Insider threats (managed via RBAC)

### RexLit

**Security Features:**
- Root-bound path resolution (13 traversal tests)
- Hash-based document access (no path injection)
- Secure symlink validation
- Offline-first design (minimal attack surface)
- Local encryption (file system level)
- Audit trail integrity verification

**Access Control:**
- File system permissions (UNIX ACLs)
- Optional web UI with hash-based routing
- API security (CLI-as-API pattern)

**Threat Model:**
- Local file system compromise
- Path traversal attacks (hardened via resolve_safe_path)
- Malicious symlinks (validated before resolution)
- Audit log tampering (detected via hash chain)

**When RexLit is better:**
- Air-gapped environments (no network exposure)
- Small teams with simple permission models
- Cases requiring local audit control
- Paranoid security postures (zero cloud trust)

**When Purview is better:**
- Enterprise environments with complex RBAC
- Organizations with SOC/compliance teams
- Distributed teams requiring remote access
- Cases requiring DLP and sensitivity labels

---

## 7. Privilege Review & Classification

### Microsoft Purview eDiscovery

**Privilege Features:**
- Manual tagging in review sets
- Filters for attorney-client keywords
- Export privilege logs
- Integration with third-party review platforms

**AI/ML Support:**
- Microsoft Security Copilot for contextual summaries
- Predictive coding for relevance (premium tier)
- No dedicated privilege classification models

**Limitations:**
- **No pattern-based privilege detection** (manual review required)
- **No LLM-powered classification** (except generic Copilot)
- **No EDRM privilege log automation**

### RexLit

**Privilege Features:**
- ✅ Pattern-based pre-filtering (≥85% confidence → skip LLM)
- ✅ LLM escalation for uncertain cases (Groq/OpenAI adapters)
- ✅ Privacy-preserving audit (hashed chain-of-thought)
- ✅ EDRM privilege log protocol compliance
- ✅ Configurable privilege policies (via CLI/UI)
- ✅ Offline fallback (pattern-based only)

**AI/ML Support:**
- Groq integration (gpt-oss-safeguard-20b, ~1-2s per doc)
- OpenAI adapter (GPT-4 fallback)
- Chain-of-thought reasoning for explainability
- Confidence scoring and rationale tracking

**When RexLit is better:**
- Small-to-medium privilege reviews (<10K documents)
- Cases requiring explainable privilege decisions
- Firms with Groq/OpenAI API access
- Offline pattern-based filtering
- EDRM privilege log requirements

**When Purview is better:**
- Large-scale privilege reviews (millions of documents)
- Teams requiring collaborative privilege tagging
- Organizations without LLM API access
- Integration with enterprise review platforms

---

## 8. Cost Comparison

### Microsoft Purview eDiscovery

**Licensing:**
- **Standard eDiscovery**: Included in E3 licenses (~$36/user/month)
- **Premium eDiscovery**: Requires E5 license (~$57/user/month) or add-ons
- **Storage**: Azure consumption fees for review sets
- **Compute**: Included in subscription (no per-document fees)

**Hidden Costs:**
- Microsoft 365 migration (if not already deployed)
- IT staff for cloud management
- Training for portal-based workflows
- Third-party tools for Bates stamping

**Total Cost of Ownership (TCO) Example:**
- 50-user law firm with E5 licenses: ~$34,200/year
- Storage and compute: Variable (typically $5K-$20K/year)
- **Estimated Annual Cost**: $40K-$55K

### RexLit

**Licensing:**
- **Open-source**: Free (license TBD)
- **Hardware**: Practitioner-owned (laptop/desktop/server)
- **Cloud costs**: Optional (Groq/OpenAI API usage only)

**Hidden Costs:**
- IT expertise for CLI setup (minimal for solo practitioners)
- Tesseract installation (free, one-time)
- LLM API usage (Groq: ~$0.10-$0.50 per 1K documents for privilege)
- Optional web UI hosting (local/self-hosted)

**Total Cost of Ownership (TCO) Example:**
- Solo practitioner or 5-user firm: $0 base cost
- LLM API usage (10K document privilege review): ~$5-$50
- **Estimated Annual Cost**: <$100 (excluding hardware)

**When RexLit is better:**
- Solo practitioners and small firms (<10 users)
- Firms without Microsoft 365 infrastructure
- Budget-constrained legal aid organizations
- Occasional eDiscovery needs (not full-time)

**When Purview is better:**
- Large enterprises with Microsoft 365 investments
- Firms with dedicated eDiscovery teams
- High-volume, continuous eDiscovery workflows
- Organizations requiring enterprise support contracts

---

## 9. Workflow Comparison

### Typical Microsoft Purview Workflow

1. **Case Creation**: Create case in Purview portal
2. **Custodian Identification**: Map users to data sources (mailboxes, OneDrive)
3. **Legal Hold**: Place holds on custodian data sources
4. **Search**: Create searches with KeyQL queries
5. **Review Set**: Add search results to cloud review set
6. **Analytics**: Run near-duplicate, threading, themes (premium tier)
7. **Review**: Tag documents in portal (or export to Relativity)
8. **Export**: Download production files from Azure

**Strengths:**
- Integrated, cloud-based workflow
- Real-time legal holds
- Collaborative review

**Weaknesses:**
- Requires constant internet
- Locked to Microsoft 365 ecosystem
- No Bates stamping

### Typical RexLit Workflow

1. **Ingest**: `rexlit ingest ./evidence --manifest out/manifest.jsonl`
2. **OCR**: `rexlit ocr run ./scans --output ./text` (if needed)
3. **Index**: `rexlit index build ./evidence`
4. **Search**: `rexlit index search "privileged AND contract" --limit 20`
5. **Privilege Review**: `rexlit privilege classify ./emails` (optional)
6. **Bates Stamping**: `rexlit bates stamp ./docs --prefix ABC --output ./stamped`
7. **Production**: `rexlit produce create ./stamped --format dat`
8. **Audit**: `rexlit audit verify`

**Strengths:**
- Complete offline processing
- CLI automation and scripting
- Deterministic, reproducible results
- Integrated Bates stamping

**Weaknesses:**
- Manual custodian data export
- No live legal holds
- Limited collaboration features

---

## 10. Use Case Decision Matrix

### Choose Microsoft Purview eDiscovery if you:

- ✅ Have an active Microsoft 365 E5 subscription
- ✅ Need to preserve data in place (legal holds)
- ✅ Work with distributed teams across time zones
- ✅ Handle millions of documents per case
- ✅ Require AI-powered analytics (predictive coding, themes)
- ✅ Need SOC 2/ISO 27001 compliance certifications
- ✅ Have dedicated IT and eDiscovery teams
- ✅ Process only Microsoft 365 data sources
- ✅ Require integration with Microsoft compliance ecosystem

### Choose RexLit if you:

- ✅ Work in air-gapped or offline environments
- ✅ Handle small-to-medium cases (<100K documents)
- ✅ Process mixed-source data (Microsoft + Google + local files)
- ✅ Need Bates stamping or court-ready load files
- ✅ Require deterministic, reproducible processing
- ✅ Have limited budget (solo/small firm)
- ✅ Need local audit trail verification
- ✅ Value open-source extensibility
- ✅ Work with scanned documents (OCR workflows)
- ✅ Require data sovereignty or regulatory compliance

---

## 11. Integration & Extensibility

### Microsoft Purview eDiscovery

**Integrations:**
- Microsoft 365 services (Exchange, Teams, SharePoint)
- Microsoft Security Copilot (AI summaries)
- Microsoft Defender (threat detection)
- Insider Risk Management (escalation workflows)
- Third-party review platforms (Relativity, etc.)

**Extensibility:**
- Closed platform (Microsoft-controlled)
- PowerShell API for automation
- Microsoft Graph API for data access
- Limited customization (portal-based)

### RexLit

**Integrations:**
- Tantivy (full-text search)
- Tesseract (OCR)
- Groq/OpenAI (privilege classification)
- Kanon 2 (dense/hybrid search)
- ICS calendar export (Outlook, Google Calendar)

**Extensibility:**
- Open-source (Python codebase)
- Ports/adapters architecture (pluggable components)
- CLI-as-API pattern (TypeScript/Bun bridge)
- Custom adapters via Protocol implementation
- Direct Python scripting

**When RexLit is better:**
- Custom workflows requiring Python scripting
- Integration with non-Microsoft systems
- Organizations with in-house dev teams
- Novel analytics or ML experiments

**When Purview is better:**
- Organizations fully invested in Microsoft ecosystem
- Need for enterprise-grade integrations
- Teams without development resources

---

## 12. Roadmap & Future Direction

### Microsoft Purview eDiscovery

**Recent Updates (2025):**
- Unified search experience (classic eDiscovery retired)
- Content Search case integration
- Enhanced data source mapping
- Security Copilot integration

**Likely Future:**
- Deeper AI integration (Copilot-driven workflows)
- Expanded Microsoft 365 service coverage
- Improved cross-cloud support (Azure, Google Workspace?)
- Advanced compliance automation

### RexLit

**Current Status (v0.2.0-m1):**
- ✅ Phase 1 (M0): Core discovery platform
- ✅ Phase 2 (M1): Production workflows (OCR, Bates, rules, privilege)
- 🚧 Phase 3 (M2): Advanced analytics (redaction, threading, graphs)

**Planned Features (M2):**
- 🚧 Redaction planning with PII detection (Presidio)
- 🚧 Email threading and family detection
- 🚧 Custodian communication graphs
- 🚧 Claude integration for privilege review
- 🚧 Paddle OCR (higher accuracy)
- 🚧 Multi-language support (Spanish, French)

**Long-term Vision:**
- Comprehensive offline-first eDiscovery toolkit
- Parity with enterprise platforms (at smaller scale)
- Community-driven adapter ecosystem
- Self-hosted web UI for team collaboration

---

## 13. Key Philosophical Differences

### Microsoft Purview: Cloud-First Enterprise Platform

**Philosophy:**
- Trust in Microsoft's cloud infrastructure
- Elastic scaling for enterprise workloads
- Integrated compliance ecosystem
- Collaboration over local control

**Trade-offs:**
- **Gain**: Unlimited scale, integrated workflows, enterprise support
- **Lose**: Data sovereignty, offline capability, cost control

### RexLit: Offline-First Open Toolkit

**Philosophy:**
- Local control and data sovereignty
- Deterministic, reproducible workflows
- Tamper-evident audit trails
- Minimal dependencies (offline-by-default)

**Trade-offs:**
- **Gain**: Privacy, cost efficiency, offline capability, extensibility
- **Lose**: Cloud scale, real-time collaboration, enterprise integrations

---

## 14. Conclusion: Which Tool to Choose?

### Microsoft Purview is the right choice for:
- **Large enterprises** with Microsoft 365 infrastructure
- **High-volume, continuous eDiscovery** workflows
- **Distributed teams** requiring real-time collaboration
- **Cases involving only Microsoft 365 data**
- **Organizations with dedicated IT/eDiscovery teams**

### RexLit is the right choice for:
- **Solo practitioners and small firms** (<10 users)
- **Air-gapped or offline environments**
- **Mixed-source productions** (Microsoft + Google + local files)
- **Cases requiring Bates stamping and court-ready load files**
- **Budget-constrained organizations** (legal aid, nonprofits)
- **Teams requiring data sovereignty or regulatory compliance**

### Hybrid Approach (Best of Both Worlds):
Some organizations may benefit from using **both** tools:
- **Purview** for initial collection and holds on Microsoft 365 data
- **Export** PST/native files from Purview
- **RexLit** for offline review, Bates stamping, and final production

---

## 15. Additional Resources

### Microsoft Purview eDiscovery
- [Microsoft Purview Documentation](https://learn.microsoft.com/en-us/purview/ediscovery)
- [Licensing Guide](https://learn.microsoft.com/en-us/office365/servicedescriptions/microsoft-365-service-descriptions/microsoft-365-tenantlevel-services-licensing-guidance/microsoft-365-security-compliance-licensing-guidance)
- [Microsoft 365 Roadmap](https://www.microsoft.com/microsoft-365/roadmap)

### RexLit
- [RexLit GitHub Repository](https://github.com/your-org/rexlit) (placeholder)
- [CLI Guide](../CLI-GUIDE.md)
- [Architecture Documentation](../CLAUDE.md)
- [Security Model](../SECURITY.md)

---

## Appendix A: Feature Parity Matrix

| Feature | Microsoft Purview | RexLit | Notes |
|---------|------------------|--------|-------|
| **Data Collection** |||
| Microsoft 365 sources | ✅ Native | ❌ Manual export | Purview has direct API access |
| Local file systems | ❌ Not supported | ✅ Native | RexLit primary use case |
| Legal holds | ✅ Yes | ❌ No | Purview can preserve data in place |
| **Search & Analytics** |||
| Full-text search | ✅ KeyQL | ✅ Tantivy (BM25) | Both support boolean queries |
| Dense/hybrid search | ❌ No | ✅ Kanon 2 (online) | RexLit has vector search option |
| Near-duplicate detection | ✅ Premium | 🚧 Planned (M2) | Purview premium tier only |
| Email threading | ✅ Yes | 🚧 Planned (M2) | Purview has native support |
| Themes analysis | ✅ Premium | ❌ No | ML-based topic modeling |
| Predictive coding | ✅ Premium | ❌ No | AI-powered relevance |
| **Privilege Review** |||
| Manual tagging | ✅ Yes | ✅ Yes | Both support manual workflows |
| Pattern-based detection | ❌ No | ✅ Yes | RexLit pre-filters at 85% confidence |
| LLM classification | ⚠️ Generic (Copilot) | ✅ Dedicated (Groq/OpenAI) | RexLit has purpose-built privilege models |
| EDRM privilege log | ⚠️ Manual | ✅ Automated | RexLit generates compliant logs |
| **Production & Export** |||
| Native file export | ✅ Yes | ✅ Yes | Both support original formats |
| DAT load files | ✅ Yes | ✅ Yes | Court-ready production files |
| Bates stamping | ❌ No | ✅ Yes | RexLit has layout-aware stamping |
| Redaction | ✅ Premium | 🚧 Planned (M2) | Purview has redaction support |
| **Compliance & Audit** |||
| Audit trail | ✅ Cloud logs | ✅ Local hash chain | Different trust models |
| Deterministic processing | ❌ No | ✅ Yes | RexLit guarantees reproducibility |
| SOC 2 / ISO 27001 | ✅ Microsoft-certified | ⚠️ User-managed | Depends on deployment |
| **Deployment** |||
| Cloud-based | ✅ Azure | ❌ No | Purview is cloud-only |
| On-premises | ❌ No | ✅ Yes | RexLit is local-first |
| Offline operation | ❌ No | ✅ Yes | RexLit designed for air-gapped use |
| **Pricing** |||
| Subscription model | ✅ E5 license | ❌ No | Purview requires Microsoft 365 |
| Open-source | ❌ No | ✅ Yes (TBD license) | RexLit is free to use |
| Per-user cost | ~$57/month | $0 | Significant cost difference |

**Legend:**
- ✅ Fully supported
- ⚠️ Partial support or requires workarounds
- ❌ Not supported
- 🚧 Planned/in development

---

## Appendix B: Migration Scenarios

### From Microsoft Purview to RexLit

**Why migrate?**
- Reduce ongoing subscription costs
- Gain offline processing capability
- Require Bates stamping or custom load files
- Need data sovereignty or air-gapped workflows

**Migration steps:**
1. Export data from Purview (PST, native files, load files)
2. Organize files on local file system
3. Run `rexlit ingest` to create manifest
4. Build Tantivy index with `rexlit index build`
5. Recreate searches and review workflows in RexLit CLI/UI

**Challenges:**
- Loss of real-time legal holds
- Manual recreation of custodian mappings
- Limited collaboration features

### From RexLit to Microsoft Purview

**Why migrate?**
- Scale to millions of documents
- Need cloud-based team collaboration
- Require Microsoft 365 integration
- Gain AI-powered analytics (predictive coding)

**Migration steps:**
1. Export RexLit manifests and metadata
2. Upload files to Microsoft 365 (OneDrive, SharePoint)
3. Create eDiscovery case in Purview
4. Map custodians to Microsoft 365 locations
5. Recreate searches in KeyQL syntax

**Challenges:**
- Loss of Bates stamping capability (requires third-party tools)
- Different audit trail format
- Ongoing subscription costs

---

## Appendix C: Glossary

- **BM25**: Best Matching 25, a probabilistic ranking function for full-text search
- **DAT**: Delimited text load file format for eDiscovery productions
- **EDRM**: Electronic Discovery Reference Model, industry standard for eDiscovery workflows
- **ESI**: Electronically Stored Information
- **HNSW**: Hierarchical Navigable Small World, algorithm for approximate nearest neighbor search
- **KeyQL**: Keyword Query Language, Microsoft's search syntax
- **Matryoshka Embeddings**: Variable-dimension vector embeddings for efficient storage/search
- **Opticon**: Image-based production load file format
- **PST**: Personal Storage Table, Outlook email archive format
- **RBAC**: Role-Based Access Control
- **Tantivy**: High-performance full-text search library (Rust-based)

---

**Document Version:** 1.0
**Feedback:** Please submit issues or questions to [repository link]
