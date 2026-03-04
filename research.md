# Technical, Legal, and Regulatory Feasibility Study: Automatic Building Fee Refund Eligibility Detection System in Israel

## Document Overview

This research paper examines whether a software system can automatically determine building permit fee refund eligibility in Israel by analyzing a physical address. The study explores technological, legal, procedural, and regulatory dimensions of creating such a PropTech system.

## Key Findings

### Legal Framework
The system must operate within Israel's Planning and Building Law (1965) and associated regulations. Building fees ("agrot binyan") fund administrative costs of local planning committees. The fundamental question centers on when refunds are due when permit applications are withdrawn or rejected.

### Landmark Supreme Court Ruling (July 2024)
A critical 2024 Supreme Court decision established that refunds of deposit payments are due **only** when authorities actively reject applications on planning grounds. Crucially, refunds are **not** owed when applicants abandon projects or fail to meet conditions imposed by authorities. This distinction requires sophisticated text analysis capabilities.

### System Architecture Requirements

The proposed system needs multiple integrated components:

1. **Address-to-Cadastral Conversion**: Transform free-text addresses into official plot/block numbers using GovMap APIs
2. **Data Integration**: Query national planning databases (MAVAT), municipal open data portals, and CKAN-based government data platforms
3. **Natural Language Processing**: Analyze committee meeting protocols and decisions to classify rejection causes accurately
4. **Historical Filtering**: Limit searches to seven-year statute of limitations window for civil claims

### Critical Constraints

**Privacy Barriers**: Financial transaction data remains protected under Israel's Privacy Protection Law. Municipal payment records cannot be accessed through public APIs, preventing full automation of refund verification.

**Data Standardization Issues**: Over 120 local planning committees maintain heterogeneous databases with varying API standards, limiting scalability across municipalities.

**Technical Challenges**: Analyzing engineering drawings and calculating area discrepancies (particularly regarding demolition credits) requires advanced computer vision capabilities currently unavailable in commercial PropTech solutions.

### Practical Implementation Model

Rather than fully autonomous verification, the study recommends a **human-in-the-loop hybrid system** functioning as initial triage:

- Automated detection flags potential refund cases within seconds
- System identifies relevant decisions and statutory exemptions
- Professional reviewers conduct detailed verification using submitted documentation
- This approach balances AI efficiency with legal accuracy requirements

### Market Opportunity

The document notes that "significant capital remains in local authority coffers" due to information gaps, complexity, and bureaucratic obstacles preventing legitimate refund claims. Current market participants include specialized tax consulting firms that manually review cases.

## Conclusion

Automated building fee refund detection is technologically feasible but requires pragmatic design acknowledging Israel's regulatory environment, privacy protections, and municipal data fragmentation. A system combining algorithmic flagging with professional human review offers the most viable path to unlocking withheld municipal funds while maintaining legal compliance.
