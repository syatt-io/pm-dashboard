# Epic Templates Feature Guide

**Last Updated**: 2025-11-17
**Status**: ✅ Complete as Admin Tool | ⏳ 30% Complete for Intended Purpose

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Feature Purpose & Business Value](#feature-purpose--business-value)
3. [Current Implementation](#current-implementation)
4. [Technical Architecture](#technical-architecture)
5. [User Guide](#user-guide)
6. [Integration Status](#integration-status)
7. [Code References](#code-references)
8. [Database Schema](#database-schema)
9. [Future Work](#future-work)
10. [Recommendations](#recommendations)

---

## Executive Summary

The **Epic Templates** feature is a fully implemented admin-only management interface for creating and maintaining standardized epic definitions. It was built as part of a larger Epic Forecasting Enhancement initiative but is currently **not yet integrated** with the forecasting workflow.

**Current State**:
- ✅ **100% Complete** as standalone admin CRUD interface
- ⏳ **30% Complete** toward intended forecasting integration
- 🎯 **Purpose**: Support AI-driven project forecasting with standardized epic hour estimates
- 🔒 **Access**: Admin users only
- 📍 **Route**: `/epic-templates`

**Key Gap**: Templates exist as data-only - they are not consumed by forecasting service or Jira export workflows.

---

## Feature Purpose & Business Value

### Problem Statement

When generating project forecasts, the system needs to:
1. Break down total project hours into **epic-level estimates**
2. Provide **consistent epic naming** across projects
3. Offer **typical hour ranges** to guide AI allocations
4. Enable **export to Jira** with fuzzy matching to existing epics

### Intended Solution

**Epic Templates** serve as a library of reusable epic definitions that:
- Standardize epic names across all projects (e.g., "Discovery", "Frontend Build")
- Store typical min/max hour ranges for each epic type
- Guide AI during forecast generation
- Facilitate Jira integration via fuzzy name matching

### Example Template Definitions

Common epics that appear across most software projects:
- **Discovery** - Requirements gathering, research, competitive analysis
- **Design System** - UI/UX design, component library, style guide
- **Frontend Build** - Client-side implementation (React, Vue, etc.)
- **Backend API** - Server-side logic, database, endpoints
- **QA/Testing** - Test planning, automation, manual testing
- **Deployment** - CI/CD, infrastructure, DevOps
- **Project Management** - Planning, meetings, coordination

---

## Current Implementation

### What's Working ✅

**Admin Interface** at `/epic-templates`:
- **Create** new epic templates with form validation
- **Edit** existing templates (inline editing)
- **Delete** templates with confirmation dialog
- **Reorder** templates via drag-and-drop (persists to DB)
- **View** all templates in clean Material-UI table
- **Search/Filter** (built into table component)
- **Loading States** for async operations
- **Error Handling** with snackbar notifications
- **Access Control** - Admin-only with JWT auth

**API Endpoints**:
- `GET /api/epic-templates` - Fetch all templates (ordered)
- `POST /api/epic-templates` - Create new template
- `PUT /api/epic-templates/<id>` - Update template
- `DELETE /api/epic-templates/<id>` - Delete template
- `POST /api/epic-templates/reorder` - Update display order

**Database**:
- Table: `standard_epic_templates`
- Fields: name (unique), description, min/max hours, order, timestamps
- Migration: `1923d6037f6e` (applied 2025-11-09)

### What's Missing ⏳

**Forecasting Integration**:
- Forecasting service does NOT fetch or use templates
- Generated forecasts lack epic-level breakdowns
- No AI allocation of hours to template epics
- File: `src/services/forecasting_service.py` has no template references

**Jira Export Workflow**:
- Backend fuzzy matching endpoint exists (`/api/forecasts/match-jira-epics`)
- NO frontend "Export to Jira" button/modal
- Cannot test template → Jira epic matching
- Cannot create/link Jira epics from forecasts

**Project Characteristics**:
- Backend API exists (`/api/projects/<key>/characteristics`)
- Frontend sliders NOT added to Projects component
- Cannot configure project complexity factors (1-5 scales)
- File: `frontend/src/components/Projects.tsx` needs update

---

## Technical Architecture

### Frontend Stack

**Component**: `frontend/src/components/EpicTemplates.tsx` (460 lines)

**Technologies**:
- React functional components with hooks
- Material-UI (Table, Dialog, TextField, IconButton, Snackbar)
- `@hello-pangea/dnd` for drag-and-drop reordering
- `react-admin` AdminLayout for consistent UI
- JWT token from localStorage for auth

**State Management**:
- Local React state (useState)
- No Redux/global state required
- Optimistic UI updates for drag-and-drop
- Loading/error states per operation

**Key Functions**:
```javascript
// Fetch all templates from API
const fetchTemplates = async () => { /* GET /api/epic-templates */ }

// Save template (create or update)
const handleSaveTemplate = async () => { /* POST or PUT */ }

// Delete template with confirmation
const handleDeleteTemplate = async (id) => { /* DELETE */ }

// Drag-and-drop reorder handler
const handleDragEnd = async (result) => { /* POST /reorder */ }
```

### Backend Stack

**Blueprint**: `src/routes/epic_templates.py` (188 lines)

**Technologies**:
- Flask Blueprint pattern
- SQLAlchemy ORM for database access
- JWT authentication (`@auth_required` decorator)
- JSON request/response format
- CSRF exempt (for React frontend)

**Endpoint Details**:

| Method | Endpoint | Description | Auth | Returns |
|--------|----------|-------------|------|---------|
| GET | `/api/epic-templates` | Fetch all templates | JWT | 200 + list |
| POST | `/api/epic-templates` | Create new template | JWT | 201 + object |
| PUT | `/api/epic-templates/<id>` | Update template | JWT | 200 + object |
| DELETE | `/api/epic-templates/<id>` | Delete template | JWT | 200 + message |
| POST | `/api/epic-templates/reorder` | Update order | JWT | 200 + message |

**Validation Logic**:
- Name uniqueness check on create/update
- Name required (cannot be empty)
- Hours must be positive integers if provided
- Order auto-assigned if not specified

**Error Handling**:
- 400 for validation errors (duplicate name, missing fields)
- 404 for template not found
- 500 for database errors
- Clear error messages in JSON response

### Database Model

**File**: `src/models/standard_epic_template.py` (56 lines)

**Model Definition**:
```python
class StandardEpicTemplate(Base):
    __tablename__ = 'standard_epic_templates'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    typical_hours_min = Column(Integer, nullable=True)
    typical_hours_max = Column(Integer, nullable=True)
    order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'typical_hours_min': self.typical_hours_min,
            'typical_hours_max': self.typical_hours_max,
            'order': self.order,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
```

**Indexes**:
- Primary key on `id`
- Unique index on `name` (prevents duplicates)

**Constraints**:
- `name` must be unique and non-null
- `order` defaults to 0 if not specified
- Timestamps auto-managed by SQLAlchemy

### Integration Points

**Registered in Flask App** (`src/web_interface.py`):
```python
# Line 332: Import blueprint
from src.routes.epic_templates import epic_templates_bp

# Line 400: Exempt from CSRF protection
csrf.exempt(epic_templates_bp)
logger.info("✅ Epic Templates endpoints exempted from CSRF protection")

# Line 447: Register blueprint
app.register_blueprint(epic_templates_bp)
```

**Added to React Navigation** (`frontend/src/App.tsx`):
```javascript
// Line 37: Import component
import EpicTemplates from './components/EpicTemplates';

// Lines 132-138: Admin menu item
{isAdmin && (
  <Menu.Item name="epic-templates">
    <Category />
    <span>Epic Templates</span>
  </Menu.Item>
)}

// Line 162: Route registration
<Route path="/epic-templates" element={<EpicTemplates />} />
```

---

## User Guide

### Accessing the Feature

1. **Login** as admin user (role check on frontend)
2. **Navigate** to Admin section in left sidebar
3. **Click** "Epic Templates" (Category icon)
4. **View** existing templates in table format

### Creating a Template

1. Click **"Add Template"** button (top right)
2. Fill in the dialog form:
   - **Template Name** (required) - e.g., "Frontend Build"
   - **Description** (optional) - Brief explanation of epic scope
   - **Typical Min Hours** (optional) - Lower bound estimate
   - **Typical Max Hours** (optional) - Upper bound estimate
3. Click **"Save"** to create
4. Success notification appears on save
5. New template appears at bottom of table

### Editing a Template

1. Locate template row in table
2. Click **Edit icon** (pencil) on right side
3. Modify fields in dialog (same form as create)
4. Click **"Save"** to update
5. Changes reflect immediately in table

### Deleting a Template

1. Locate template row in table
2. Click **Delete icon** (trash) on right side
3. Confirm deletion in dialog prompt
4. Template removed from table on success
5. Warning: Cannot be undone

### Reordering Templates

1. Hover over **drag handle** (six dots) on left of any row
2. Click and hold to grab row
3. Drag row up or down to desired position
4. Release to drop in new position
5. Order persists to database automatically
6. Use reordering to prioritize important epics

### Table Features

- **Sortable columns** - Click column headers to sort
- **Search** - Use table search bar to filter templates
- **Pagination** - If >25 templates, use page controls
- **Responsive** - Table adjusts to screen size

---

## Integration Status

### Completed Components ✅

| Component | Status | File | Lines |
|-----------|--------|------|-------|
| Frontend UI | ✅ Complete | `frontend/src/components/EpicTemplates.tsx` | 1-460 |
| Backend API | ✅ Complete | `src/routes/epic_templates.py` | 1-188 |
| Database Model | ✅ Complete | `src/models/standard_epic_template.py` | 1-56 |
| Database Migration | ✅ Applied | `alembic/versions/1923d6037f6e_*.py` | 25-42 |
| Navigation Item | ✅ Complete | `frontend/src/App.tsx` | 132-138 |
| Flask Registration | ✅ Complete | `src/web_interface.py` | 332, 400, 447 |
| CSRF Exemption | ✅ Complete | `src/web_interface.py` | 400 |

### Incomplete Integrations ⏳

| Component | Status | Missing Work | Priority |
|-----------|--------|--------------|----------|
| Forecasting Service | ❌ Not Started | Fetch templates, allocate hours to epics | High |
| ProjectForecastTab UI | ❌ Not Started | Display epic breakdowns in forecast results | High |
| Export to Jira Modal | ❌ Not Started | Frontend UI to trigger export workflow | Medium |
| Jira Fuzzy Matching | ⏳ Backend Only | Frontend integration needed | Medium |
| Project Characteristics | ⏳ Backend Only | Add sliders to Projects component | Low |
| Seed Data Migration | ❌ Not Started | Populate default templates for first-time users | Low |

### Dependency Chain

To achieve full integration, work must proceed in this order:

1. **Update Forecasting Service** (`src/services/forecasting_service.py`)
   - Fetch templates from database
   - Prompt AI to allocate hours by epic
   - Store epic-level breakdown in forecast results

2. **Enhance ProjectForecastTab** (`frontend/src/components/ProjectForecastTab.tsx`)
   - Display epic breakdowns in results table
   - Show allocated hours per epic
   - Allow editing epic allocations

3. **Build Export to Jira Modal** (new component)
   - "Export to Jira" button in forecast results
   - Fetch existing Jira epics for project
   - Fuzzy match template names to Jira epic names
   - Allow user to create new epics or link existing
   - Call backend to create Jira epics

4. **Add Project Characteristics UI** (`frontend/src/components/Projects.tsx`)
   - 6 sliders (1-5 scale) for complexity factors
   - Save to backend via existing API
   - Use characteristics to filter/weight templates

---

## Code References

### Frontend Files

**Main Component**:
- `frontend/src/components/EpicTemplates.tsx` (460 lines)
  - Lines 89-111: `fetchTemplates()` - API fetch function
  - Lines 153-193: `handleSaveTemplate()` - Create/update logic
  - Lines 195-223: `handleDeleteTemplate()` - Delete with confirmation
  - Lines 225-262: `handleDragEnd()` - Reorder via drag-and-drop
  - Lines 264-377: Main render - Table with drag-and-drop rows
  - Lines 379-442: `renderDialog()` - Create/Edit form modal

**Navigation**:
- `frontend/src/App.tsx`
  - Line 37: `import EpicTemplates from './components/EpicTemplates';`
  - Lines 132-138: Admin menu item with Category icon
  - Line 162: `<Route path="/epic-templates" element={<EpicTemplates />} />`

### Backend Files

**Blueprint**:
- `src/routes/epic_templates.py` (188 lines)
  - Lines 17-34: `get_templates()` - GET all (ordered by order field)
  - Lines 37-82: `create_template()` - POST create with validation
  - Lines 85-133: `update_template()` - PUT update (checks name conflicts)
  - Lines 136-159: `delete_template()` - DELETE by ID
  - Lines 162-187: `reorder_templates()` - POST bulk update order field

**Model**:
- `src/models/standard_epic_template.py` (56 lines)
  - Lines 8-40: `StandardEpicTemplate` class definition
  - Lines 44-55: `to_dict()` method for JSON serialization

**Flask App**:
- `src/web_interface.py`
  - Line 332: `from src.routes.epic_templates import epic_templates_bp`
  - Line 400: `csrf.exempt(epic_templates_bp)`
  - Line 447: `app.register_blueprint(epic_templates_bp)`

### Database Files

**Migration**:
- `alembic/versions/1923d6037f6e_add_project_projectcharacteristics_and_.py`
  - Lines 25-42: `create_table('standard_epic_templates', ...)`
  - Line 37: `sa.UniqueConstraint('name', name='uq_standard_epic_templates_name')`
  - Line 38: `sa.Index('ix_standard_epic_templates_name', ...)`

**Schema Documentation**:
- `docs/DATABASE_SCHEMA.md`
  - Lines 444-454: Table schema description

### Related Documentation

**Implementation Plan**:
- `docs/EPIC_FORECASTING_IMPLEMENTATION_PLAN.md`
  - Lines 70-580: Epic Templates feature specification
  - Lines 1345-1980: Export to Jira workflow design

**Progress Tracker**:
- `docs/EPIC_FORECASTING_PROGRESS.md`
  - Lines 5-22: Epic Templates completion status (✅ Backend, ✅ Frontend)
  - Lines 101-116: Export to Jira requirements (⏳ Pending)

---

## Database Schema

### Table: `standard_epic_templates`

```sql
CREATE TABLE standard_epic_templates (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(200) NOT NULL UNIQUE,
    description TEXT,
    typical_hours_min INTEGER,
    typical_hours_max INTEGER,
    "order" INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_standard_epic_templates_name UNIQUE (name)
);

CREATE INDEX ix_standard_epic_templates_name ON standard_epic_templates (name);
```

### Column Definitions

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | NO | autoincrement | Primary key |
| `name` | VARCHAR(200) | NO | - | Epic template name (unique) |
| `description` | TEXT | YES | NULL | Optional epic description |
| `typical_hours_min` | INTEGER | YES | NULL | Minimum hour estimate |
| `typical_hours_max` | INTEGER | YES | NULL | Maximum hour estimate |
| `order` | INTEGER | NO | 0 | Display order (for drag-and-drop) |
| `created_at` | TIMESTAMP | NO | NOW | Record creation timestamp |
| `updated_at` | TIMESTAMP | NO | NOW | Last update timestamp |

### Constraints & Indexes

- **Primary Key**: `id` column (auto-increment)
- **Unique Constraint**: `name` column (prevents duplicate template names)
- **Index**: `ix_standard_epic_templates_name` on `name` (for fast lookups)
- **Timestamps**: `created_at` auto-set on insert, `updated_at` auto-updated

### Sample Data

```json
[
  {
    "id": 1,
    "name": "Discovery",
    "description": "Requirements gathering, research, competitive analysis",
    "typical_hours_min": 20,
    "typical_hours_max": 40,
    "order": 1
  },
  {
    "id": 2,
    "name": "Design System",
    "description": "UI/UX design, component library, style guide",
    "typical_hours_min": 40,
    "typical_hours_max": 80,
    "order": 2
  },
  {
    "id": 3,
    "name": "Frontend Build",
    "description": "Client-side implementation (React, Vue, etc.)",
    "typical_hours_min": 80,
    "typical_hours_max": 200,
    "order": 3
  }
]
```

### Current Data Status

**Migration Applied**: Yes (2025-11-09)
**Table Exists**: Confirmed in production schema
**Data Present**: Unknown (likely empty - no seed migration)

---

## Future Work

### Phase 1: Forecasting Integration (High Priority)

**Goal**: Use templates during forecast generation

**Tasks**:
1. **Update Forecasting Service** (`src/services/forecasting_service.py`)
   - Add function to fetch all templates from DB
   - Include templates in AI prompt context
   - Instruct AI to allocate hours to each template epic
   - Store epic-level breakdown in forecast response

2. **Enhance Forecast Results** (`frontend/src/components/ProjectForecastTab.tsx`)
   - Add "Epic Breakdown" section to results
   - Display table of epics with allocated hours
   - Show percentage of total hours per epic
   - Allow inline editing of epic allocations
   - Recalculate totals on edit

3. **Testing**
   - Generate forecast for test project
   - Verify epic-level breakdown appears
   - Validate hour totals match project estimate
   - Test with different project types/characteristics

### Phase 2: Jira Export (Medium Priority)

**Goal**: Export forecast epics to Jira with fuzzy matching

**Tasks**:
1. **Build Export Modal** (new `frontend/src/components/ExportEpicsModal.tsx`)
   - "Export to Jira" button in ProjectForecastTab
   - Fetch existing Jira epics for project (via API)
   - Display fuzzy match results in table
   - Allow user to:
     - Create new epic in Jira
     - Link to existing epic
     - Skip epic (don't export)
   - Bulk create/link on confirm

2. **Enhance Backend** (`src/routes/forecasts.py`)
   - Update `/api/forecasts/match-jira-epics` endpoint
   - Accept forecast ID instead of manual epic list
   - Load epic breakdown from forecast results
   - Return fuzzy matches with confidence scores
   - Add `/api/forecasts/<id>/export-to-jira` endpoint
   - Create Jira epics via API
   - Update forecast with Jira epic keys

3. **Testing**
   - Export forecast to test Jira project
   - Verify fuzzy matching accuracy
   - Test new epic creation
   - Test linking to existing epics
   - Validate Jira data (names, descriptions, hours)

### Phase 3: Project Characteristics (Low Priority)

**Goal**: Configure project complexity to filter/weight templates

**Tasks**:
1. **Add UI to Projects Component** (`frontend/src/components/Projects.tsx`)
   - Add "Characteristics" section to project form
   - 6 sliders (1-5 scale):
     - Technical Complexity
     - Design Complexity
     - Business Logic Complexity
     - Integration Complexity
     - Performance Requirements
     - Security Requirements
   - Save characteristics to backend API (already exists)

2. **Use in Forecasting** (`src/services/forecasting_service.py`)
   - Fetch project characteristics
   - Include in AI prompt context
   - Adjust epic hour allocations based on complexity
   - Example: High design complexity → more hours to Design System epic

3. **Testing**
   - Set different characteristics for test projects
   - Generate forecasts and compare epic allocations
   - Verify AI adjusts hours appropriately

### Phase 4: Polish & Optimization (Low Priority)

**Goal**: Improve usability and add advanced features

**Tasks**:
1. **Seed Data Migration**
   - Create Alembic migration with default templates
   - Populate 8-10 common epics on fresh install
   - Add descriptions and typical hour ranges

2. **Backend Admin Check**
   - Add `@admin_required` decorator to all epic template endpoints
   - Currently only frontend checks admin role
   - Improve security by enforcing on backend

3. **Template Categories**
   - Add `category` field to model (e.g., "Development", "Design", "Management")
   - Allow filtering templates by category
   - Use categories to organize templates in UI

4. **Template Versioning**
   - Track changes to templates over time
   - Allow restoring previous versions
   - Show change history in UI

5. **Bulk Import/Export**
   - Export templates to JSON/CSV
   - Import templates from file
   - Share templates across environments

---

## Recommendations

### Immediate Actions

1. **Create Seed Data Migration**
   - Add 8-10 common epic templates for first-time users
   - Prevents empty state on fresh install
   - Provides examples for admins

   ```bash
   alembic revision -m "Seed standard epic templates"
   # Edit migration to insert default templates
   alembic upgrade head
   ```

2. **Add Backend Admin Check**
   - Import `@admin_required` decorator in `src/routes/epic_templates.py`
   - Apply to all 5 endpoints
   - Prevents non-admin API access (currently only frontend checks)

   ```python
   from src.auth.decorators import admin_required

   @epic_templates_bp.route('/api/epic-templates', methods=['GET'])
   @auth_required
   @admin_required
   def get_templates():
       # ...
   ```

3. **Document User Workflow**
   - Add admin guide to `docs/ADMIN_GUIDE.md`
   - Include screenshots of Epic Templates interface
   - Provide best practices for template creation

### Before Starting Integration Work

1. **Review Existing Design Docs**
   - `docs/EPIC_FORECASTING_IMPLEMENTATION_PLAN.md` (lines 70-580)
   - `docs/EPIC_FORECASTING_PROGRESS.md` (lines 101-116)
   - Ensure understanding of intended workflow

2. **Create Integration Plan**
   - Break down Phase 1 (Forecasting Integration) into smaller tasks
   - Estimate effort for each task
   - Identify dependencies and blockers

3. **Set Up Test Data**
   - Create test project in Jira
   - Generate sample forecast results
   - Prepare test cases for epic allocation

### Long-Term Considerations

1. **Template Sharing**
   - Consider multi-tenant architecture (templates per organization)
   - Or global templates shared across all users

2. **AI Training**
   - Use actual epic hour data from completed projects
   - Train AI to better predict epic allocations
   - Adjust typical hour ranges based on real data

3. **Analytics**
   - Track which templates are used most often
   - Measure forecast accuracy at epic level
   - Identify templates that need hour range adjustments

---

## Troubleshooting

### Issue: Templates Not Loading

**Symptoms**: Table shows loading spinner forever

**Possible Causes**:
- JWT token expired or invalid
- Backend API not responding
- Database connection error

**Solutions**:
1. Check browser console for 401/403 errors
2. Verify JWT token in localStorage: `localStorage.getItem('token')`
3. Check Flask logs for database errors
4. Test API directly: `GET http://localhost:4000/api/epic-templates`

### Issue: Cannot Create Template

**Symptoms**: "Failed to save template" error

**Possible Causes**:
- Duplicate template name
- Missing required field (name)
- Database constraint violation

**Solutions**:
1. Check snackbar error message for specific reason
2. Ensure template name is unique
3. Verify all required fields are filled
4. Check Flask logs for validation errors

### Issue: Drag-and-Drop Not Working

**Symptoms**: Cannot reorder templates by dragging

**Possible Causes**:
- Browser compatibility issue with @hello-pangea/dnd
- Conflicting CSS styles
- Mobile device (drag-and-drop not supported)

**Solutions**:
1. Try different browser (Chrome, Firefox, Safari)
2. Check browser console for JavaScript errors
3. Disable browser extensions temporarily
4. Use desktop device (mobile not supported)

### Issue: Admin Menu Item Not Visible

**Symptoms**: Cannot find "Epic Templates" in navigation

**Possible Causes**:
- User not logged in as admin
- Frontend admin check failing
- React route not registered

**Solutions**:
1. Verify user role: Check `isAdmin` in React state
2. Check JWT token claims: Decode token at jwt.io
3. Ensure user has `role: 'admin'` in database
4. Check `frontend/src/App.tsx` lines 132-138 for route

---

## Security Considerations

### Current Security

- **Authentication**: JWT Bearer token required on all API endpoints
- **Authorization**: Admin check on frontend (Menu.Item conditional)
- **CSRF**: Blueprint exempted from CSRF protection (safe for API)
- **SQL Injection**: Prevented by SQLAlchemy ORM parameterization
- **XSS**: Prevented by React's built-in escaping

### Security Gaps

- **No Backend Admin Check**: API endpoints only check JWT, not admin role
  - Risk: Non-admin users could call API directly
  - Mitigation: Add `@admin_required` decorator to all endpoints

- **No Rate Limiting**: Could spam template creation requests
  - Risk: DOS via excessive API calls
  - Mitigation: Add rate limiting middleware

- **No Audit Log**: No record of who created/modified templates
  - Risk: Cannot trace changes back to user
  - Mitigation: Add audit log table with user ID and action

### Recommended Enhancements

1. **Backend Admin Enforcement**
   ```python
   @epic_templates_bp.route('/api/epic-templates', methods=['POST'])
   @auth_required
   @admin_required  # Add this
   def create_template():
       # ...
   ```

2. **Rate Limiting**
   ```python
   from flask_limiter import Limiter
   limiter = Limiter(app, key_func=lambda: request.headers.get('Authorization'))

   @epic_templates_bp.route('/api/epic-templates', methods=['POST'])
   @limiter.limit("10 per minute")
   @auth_required
   def create_template():
       # ...
   ```

3. **Audit Logging**
   ```python
   class EpicTemplateAudit(Base):
       id = Column(Integer, primary_key=True)
       template_id = Column(Integer, ForeignKey('standard_epic_templates.id'))
       user_id = Column(Integer, ForeignKey('users.id'))
       action = Column(String(50))  # 'created', 'updated', 'deleted'
       timestamp = Column(DateTime, default=datetime.utcnow)
       changes = Column(JSON)  # Before/after values
   ```

---

## Changelog

### 2025-11-09 - Initial Implementation
- Created `StandardEpicTemplate` model
- Created `epic_templates_bp` blueprint with 5 endpoints
- Built `EpicTemplates.tsx` React component (460 lines)
- Applied database migration `1923d6037f6e`
- Registered blueprint in Flask app
- Added navigation menu item (admin-only)
- Documented in `EPIC_FORECASTING_PROGRESS.md`

### 2025-11-17 - Feature Investigation
- Comprehensive investigation of feature status
- Discovered integration gaps (forecasting, Jira export)
- Created this feature guide document
- Identified future work and recommendations

---

## Related Documentation

- [EPIC_FORECASTING_IMPLEMENTATION_PLAN.md](./EPIC_FORECASTING_IMPLEMENTATION_PLAN.md) - Original feature specification
- [EPIC_FORECASTING_PROGRESS.md](./EPIC_FORECASTING_PROGRESS.md) - Implementation progress tracker
- [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) - Full database schema documentation
- [CSRF_PROTECTION_GUIDE.md](./CSRF_PROTECTION_GUIDE.md) - Why blueprint is CSRF-exempt

---

## Questions & Answers

### Q: Why aren't templates being used in forecasts yet?

**A**: The forecasting service (`src/services/forecasting_service.py`) was built before the Epic Templates feature. Integration requires updating the forecasting prompt to include templates and instruct the AI to allocate hours by epic. This is the top priority for future work.

### Q: Can non-admin users view templates?

**A**: No. The navigation menu item is admin-only (`{isAdmin && <Menu.Item ...>}`). The API endpoints require JWT auth but don't explicitly check admin role - this should be added for security.

### Q: How does drag-and-drop reordering work?

**A**: The frontend uses `@hello-pangea/dnd` (successor to react-beautiful-dnd). On drop, it calculates the new order for all templates and sends a `POST /api/epic-templates/reorder` request with the new order array. The backend updates the `order` field for each template.

### Q: Can templates be deleted if they're used in forecasts?

**A**: Currently yes, because templates are not yet integrated. Once integration is complete, you should add a foreign key constraint or soft delete to prevent breaking existing forecasts.

### Q: What happens if two admins edit the same template simultaneously?

**A**: Last write wins (optimistic concurrency). The `updated_at` timestamp will show the most recent change, but earlier changes are lost. For production, consider adding version field and conflict detection.

### Q: How do I add more fields to templates?

**A**:
1. Update `StandardEpicTemplate` model in `src/models/standard_epic_template.py`
2. Create Alembic migration: `alembic revision --autogenerate -m "Add field to epic templates"`
3. Apply migration: `alembic upgrade head`
4. Update `to_dict()` method to include new field
5. Update API endpoints to accept new field in POST/PUT
6. Update React component to display/edit new field

---

## Conclusion

The Epic Templates feature is a **fully functional admin tool** that successfully provides CRUD operations for managing standardized epic definitions. The implementation is clean, well-structured, and production-ready as a standalone feature.

However, it represents only **30% of the intended functionality** because templates are not yet consumed by the forecasting service or Jira export workflows. The feature exists in isolation and does not yet deliver its core business value.

**Next Steps**: Prioritize Phase 1 (Forecasting Integration) to connect templates to the forecast generation process. This will unlock the feature's primary use case and justify its existence in the codebase.

For questions or to continue implementation, refer to the code references and future work sections above.
