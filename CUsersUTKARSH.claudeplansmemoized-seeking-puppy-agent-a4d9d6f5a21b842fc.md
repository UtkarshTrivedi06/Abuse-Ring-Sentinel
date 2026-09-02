# Implementation Plan: UI Overhaul & Supabase Integration

## 1. UI Overhaul (`frontend/index.html`)

### Design Specification
- **Theme**: Cyber-security Professional
- **Palette**:
    - Void Black: `#04060C` (Background)
    - Deep Navy: `#080C16` (Surface)
    - Amber: `#F59E0B` (Warning/Flagged)
    - Teal: `#10B981` (Safe/Cleared)
    - Violet: `#8B5CF6` (AI/Insight)
- **Layout**: Tabbed Interface ([Dashboard], [Graph Analysis])

### Component Breakdown

#### A. Tab Navigation
- Fixed top navigation bar with high-contrast active states.

#### B. Dashboard Tab
- **Stats Row**: 4-5 Glassmorphism cards (Total Orders, Flagged Rings, Recall, Queue Reduction).
- **Middle Section (Split View)**:
    - **AI Analysis Feed**: A scrolling terminal-like log showing simulated real-time AI decisions (e.g., "Evaluating Cluster #4... Topology Match: High... Risk Score: 8.2... Flagging for Review").
    - **Priority Review Queue**: A professional table listing flagged rings with columns: Cluster ID, Risk Weight, Size, Primary Attributes.
- **Bottom Section (AI Insight Card)**:
    - Detailed view of the selected ring.
    - **Reasoning Path Visualization**: A step-by-step flow (Attribute Matching $\rightarrow$ Topology Analysis $\rightarrow$ Risk Scoring) using arrows and icons to show how the AI reached the decision.

#### C. Graph Analysis Tab
- **Full-screen Graph**: `vis-network` integration occupying the entire viewport.
- **Interactivity**:
    - Hover Tooltips: Order ID, Value, KYC status.
    - Click Action: Selecting a node updates the AI Insight Card (which should be rendered in a persistent bottom panel accessible from both tabs).

### Technical Implementation (Frontend)
- **Styling**: Replace custom CSS with Tailwind CSS for layout and spacing, while keeping custom CSS variables for the specific palette.
- **State Management**: A global `state` object to track `selectedClusterId` and `currentTab`.
- **Componentization**: Break the UI into JS functions that render HTML strings for better maintainability.

---

## 2. Database Integration (Supabase)

### Supabase Schema (SQL)

```sql
-- Orders Table
CREATE TABLE orders (
    id TEXT PRIMARY KEY,
    value NUMERIC,
    kyc_verified BOOLEAN,
    account_created_at DATE,
    shipping_address TEXT,
    device_id TEXT,
    promo_code TEXT,
    is_injected_ring BOOLEAN DEFAULT FALSE
);

-- Clusters Table
CREATE TABLE clusters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    total_weight NUMERIC,
    flagged BOOLEAN,
    explanation TEXT,
    confidence_score NUMERIC,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Cluster Members (Join Table)
CREATE TABLE cluster_members (
    cluster_id UUID REFERENCES clusters(id) ON DELETE CASCADE,
    order_id TEXT REFERENCES orders(id) ON DELETE CASCADE,
    PRIMARY KEY (cluster_id, order_id)
);
```

### Pipeline Modifications (`agent.py`)

1.  **Dependency**: Add `supabase` to `requirements.txt`.
2.  **Client Setup**: Initialize `supabase` client using environment variables (`SUPABASE_URL`, `SUPABASE_KEY`).
3.  **Data Upload Phase**: Create `phase6_upload_to_supabase(orders, explained_clusters, report)`:
    - **Orders**: Bulk insert `orders` list into `orders` table.
    - **Clusters**: Bulk insert `explained_clusters` (excluding member IDs) into `clusters` table.
    - **Members**: For each created cluster, map its `order_ids` and insert into `cluster_members`.
    - **Audit**: Store `report` metrics in a separate `audit_logs` table or as a JSONB metadata entry.

### Frontend Integration (`index.html`)

1.  **SDK Integration**: Add `<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>`.
2.  **Data Fetching**: Replace `fetch('dashboard_data.json')` with:
    - `supabase.from('clusters').select('*')` to get the review queue.
    - `supabase.from('cluster_members').select('orders(*)')` for member details.
    - `supabase.rpc('get_dashboard_stats')` (or client-side aggregation) for the stats cards.

---

## 3. Fallback & Compatibility Strategy

To ensure the app works without a database:

1.  **Hybrid Data Loader**:
    - Implement a `DataLoader` class in JS that first attempts to initialize the Supabase client.
    - If Supabase fails (no config or network error), it falls back to `fetch('dashboard_data.json')`.
2.  **Parallel Pipeline**:
    - `agent.py` will continue to generate `frontend/dashboard_data.json` via `build_dashboard_data.py`.
    - The Supabase upload becomes an optional "enhancement" phase that can be skipped if credentials are missing.
3.  **Config-driven Source**:
    - Add a hidden config object `const APP_CONFIG = { dataSource: 'supabase' // or 'json' }` to allow developers to switch sources easily.

## 4. Implementation Steps

1.  **Step 1**: Update `requirements.txt` and install `supabase`.
2.  **Step 2**: Implement Supabase schema in the Supabase console.
3.  **Step 3**: Modify `agent.py` to add the Supabase upload logic.
4.  **Step 4**: Redesign `index.html` HTML structure for tabs and the new Dashboard layout using Tailwind.
5.  **Step 5**: Implement the "AI Analysis Feed" simulation and "Reasoning Path" visualization in JS.
6.  **Step 6**: Integrate `vis-network` into the Graph tab with the required tooltips and click-events.
7.  **Step 7**: Implement the `DataLoader` in `index.html` to handle Supabase $\rightarrow$ JSON fallback.
8.  **Step 8**: Final styling pass for the "Cyber-security" theme.
EOF`
