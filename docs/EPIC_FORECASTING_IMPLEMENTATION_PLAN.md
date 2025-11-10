# Epic Analysis & Forecasting Enhancement - Implementation Plan

**Status**: In Progress
**Created**: 2025-01-09
**Estimated Effort**: 25-33 hours

---

## Overview

This document provides a complete implementation guide for enhancing the forecasting system with:
1. Analytics button to rebuild forecasting models from production data
2. Project characteristics configuration for historical data
3. Epic-level breakdown by month in forecast UI
4. Standard epic templates management
5. Export forecast epics to Jira with fuzzy matching

---

## ✅ Completed Tasks

### 1. Database Models Created
**Files Created**:
- `src/models/project.py` - Project and ProjectCharacteristics models
- `src/models/standard_epic_template.py` - StandardEpicTemplate model
- `src/models/__init__.py` - Updated with new imports

**Models**:
```python
# Project - Core project metadata
class Project(Base):
    key: str (PK)
    name: str
    is_active: bool
    created_at, updated_at: DateTime
    characteristics: relationship -> ProjectCharacteristics

# ProjectCharacteristics - Forecasting parameters
class ProjectCharacteristics(Base):
    id: int (PK)
    project_key: str (FK -> projects.key, unique)
    be_integrations: int (1-5)
    custom_theme: int (1-5)
    custom_designs: int (1-5)
    ux_research: int (1-5)
    extensive_customizations: int (1-5)
    project_oversight: int (1-5)
    blend_factor: property (calculated from be_integrations)

# StandardEpicTemplate - Reusable epic definitions
class StandardEpicTemplate(Base):
    id: int (PK)
    name: str (unique)
    description: Text
    typical_hours_min, typical_hours_max: int
    order: int (for display sorting)
```

### 2. Database Migration Applied
**Migration**: `1923d6037f6e` - "Add Project, ProjectCharacteristics, and StandardEpicTemplate tables"
**Status**: ✅ Applied successfully
**Command**: `alembic upgrade head`

---

## 🔨 Implementation Tasks

### Feature 1: Standard Epic Templates Management

#### Backend API (`src/routes/epic_templates.py`)

**Create New Route File**:
```python
"""Epic Templates management routes."""
from flask import Blueprint, jsonify, request
import logging
from src.services.auth import auth_required
from src.utils.database import session_scope
from src.models import StandardEpicTemplate

logger = logging.getLogger(__name__)

epic_templates_bp = Blueprint('epic_templates', __name__, url_prefix='/api/epic-templates')


@epic_templates_bp.route('', methods=['GET'])
@auth_required
def get_epic_templates(user):
    """Get all epic templates, ordered by display order."""
    try:
        with session_scope() as db:
            templates = db.query(StandardEpicTemplate)\
                .order_by(StandardEpicTemplate.order)\
                .all()

            return jsonify({
                'success': True,
                'templates': [t.to_dict() for t in templates]
            })
    except Exception as e:
        logger.error(f"Failed to get epic templates: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@epic_templates_bp.route('', methods=['POST'])
@auth_required
def create_epic_template(user):
    """Create a new epic template."""
    try:
        data = request.json

        # Validate required fields
        if not data.get('name'):
            return jsonify({'success': False, 'error': 'Name is required'}), 400

        with session_scope() as db:
            # Check for duplicate name
            existing = db.query(StandardEpicTemplate)\
                .filter_by(name=data['name'])\
                .first()

            if existing:
                return jsonify({'success': False, 'error': 'Template with this name already exists'}), 400

            # Get max order for new template
            max_order = db.query(db.func.max(StandardEpicTemplate.order)).scalar() or 0

            template = StandardEpicTemplate(
                name=data['name'],
                description=data.get('description'),
                typical_hours_min=data.get('typical_hours_min'),
                typical_hours_max=data.get('typical_hours_max'),
                order=max_order + 1
            )
            db.add(template)
            db.flush()

            return jsonify({
                'success': True,
                'template': template.to_dict()
            }), 201

    except Exception as e:
        logger.error(f"Failed to create epic template: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@epic_templates_bp.route('/<int:template_id>', methods=['PUT'])
@auth_required
def update_epic_template(user, template_id):
    """Update an existing epic template."""
    try:
        data = request.json

        with session_scope() as db:
            template = db.query(StandardEpicTemplate).get(template_id)

            if not template:
                return jsonify({'success': False, 'error': 'Template not found'}), 404

            # Check for name conflict if name is being changed
            if data.get('name') and data['name'] != template.name:
                existing = db.query(StandardEpicTemplate)\
                    .filter_by(name=data['name'])\
                    .first()

                if existing:
                    return jsonify({'success': False, 'error': 'Template with this name already exists'}), 400

                template.name = data['name']

            # Update other fields
            if 'description' in data:
                template.description = data['description']
            if 'typical_hours_min' in data:
                template.typical_hours_min = data['typical_hours_min']
            if 'typical_hours_max' in data:
                template.typical_hours_max = data['typical_hours_max']
            if 'order' in data:
                template.order = data['order']

            db.flush()

            return jsonify({
                'success': True,
                'template': template.to_dict()
            })

    except Exception as e:
        logger.error(f"Failed to update epic template {template_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@epic_templates_bp.route('/<int:template_id>', methods=['DELETE'])
@auth_required
def delete_epic_template(user, template_id):
    """Delete an epic template."""
    try:
        with session_scope() as db:
            template = db.query(StandardEpicTemplate).get(template_id)

            if not template:
                return jsonify({'success': False, 'error': 'Template not found'}), 404

            db.delete(template)

            return jsonify({
                'success': True,
                'message': f'Template "{template.name}" deleted successfully'
            })

    except Exception as e:
        logger.error(f"Failed to delete epic template {template_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@epic_templates_bp.route('/reorder', methods=['POST'])
@auth_required
def reorder_templates(user):
    """Reorder epic templates."""
    try:
        data = request.json
        template_ids = data.get('template_ids', [])

        if not template_ids:
            return jsonify({'success': False, 'error': 'template_ids required'}), 400

        with session_scope() as db:
            for idx, template_id in enumerate(template_ids):
                template = db.query(StandardEpicTemplate).get(template_id)
                if template:
                    template.order = idx

            db.flush()

            return jsonify({
                'success': True,
                'message': 'Templates reordered successfully'
            })

    except Exception as e:
        logger.error(f"Failed to reorder templates: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
```

**Register Blueprint in `main.py`**:
```python
# Import blueprint
from src.routes.epic_templates import epic_templates_bp

# Register blueprint
app.register_blueprint(epic_templates_bp)

# Don't forget CSRF exemption!
from flask_wtf.csrf import CSRFProtect
csrf = CSRFProtect(app)
csrf.exempt(epic_templates_bp)
logger.info("✅ Epic Templates endpoints exempted from CSRF protection")
```

#### Frontend UI (`frontend/src/components/EpicTemplates.tsx`)

**Create New Component**:
```typescript
import React, { useState, useEffect } from 'react';
import { DragDropContext, Droppable, Draggable } from 'react-beautiful-dnd';
import { API_BASE_URL } from '../config';

interface EpicTemplate {
  id: number;
  name: string;
  description?: string;
  typical_hours_min?: number;
  typical_hours_max?: number;
  order: number;
  created_at: string;
  updated_at: string;
}

const EpicTemplates: React.FC = () => {
  const [templates, setTemplates] = useState<EpicTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    typical_hours_min: '',
    typical_hours_max: ''
  });

  useEffect(() => {
    fetchTemplates();
  }, []);

  const fetchTemplates = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/api/epic-templates`, {
        credentials: 'include'
      });
      const data = await response.json();

      if (data.success) {
        setTemplates(data.templates);
      }
    } catch (error) {
      console.error('Failed to fetch templates:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/epic-templates`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          name: formData.name,
          description: formData.description || null,
          typical_hours_min: formData.typical_hours_min ? parseInt(formData.typical_hours_min) : null,
          typical_hours_max: formData.typical_hours_max ? parseInt(formData.typical_hours_max) : null
        })
      });

      const data = await response.json();

      if (data.success) {
        setTemplates([...templates, data.template]);
        setShowCreateForm(false);
        setFormData({ name: '', description: '', typical_hours_min: '', typical_hours_max: '' });
      } else {
        alert(`Error: ${data.error}`);
      }
    } catch (error) {
      console.error('Failed to create template:', error);
      alert('Failed to create template');
    }
  };

  const handleUpdate = async (id: number, updates: Partial<EpicTemplate>) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/epic-templates/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(updates)
      });

      const data = await response.json();

      if (data.success) {
        setTemplates(templates.map(t => t.id === id ? data.template : t));
        setEditingId(null);
      } else {
        alert(`Error: ${data.error}`);
      }
    } catch (error) {
      console.error('Failed to update template:', error);
      alert('Failed to update template');
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this template?')) return;

    try {
      const response = await fetch(`${API_BASE_URL}/api/epic-templates/${id}`, {
        method: 'DELETE',
        credentials: 'include'
      });

      const data = await response.json();

      if (data.success) {
        setTemplates(templates.filter(t => t.id !== id));
      } else {
        alert(`Error: ${data.error}`);
      }
    } catch (error) {
      console.error('Failed to delete template:', error);
      alert('Failed to delete template');
    }
  };

  const handleDragEnd = async (result: any) => {
    if (!result.destination) return;

    const items = Array.from(templates);
    const [reorderedItem] = items.splice(result.source.index, 1);
    items.splice(result.destination.index, 0, reorderedItem);

    setTemplates(items);

    // Update order on backend
    try {
      await fetch(`${API_BASE_URL}/api/epic-templates/reorder`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          template_ids: items.map(t => t.id)
        })
      });
    } catch (error) {
      console.error('Failed to reorder templates:', error);
      alert('Failed to save new order');
      fetchTemplates(); // Reload from server
    }
  };

  return (
    <div className="epic-templates-container" style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h2>Standard Epic Templates</h2>
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          style={{
            background: '#554DFF',
            color: 'white',
            border: 'none',
            padding: '10px 20px',
            borderRadius: '5px',
            cursor: 'pointer'
          }}
        >
          {showCreateForm ? 'Cancel' : '+ Add Template'}
        </button>
      </div>

      {showCreateForm && (
        <div style={{
          background: '#f5f5f5',
          padding: '20px',
          borderRadius: '8px',
          marginBottom: '20px'
        }}>
          <h3>Create New Template</h3>
          <div style={{ display: 'grid', gap: '15px' }}>
            <div>
              <label>Name *</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., Discovery, Design System, Frontend Build"
                style={{ width: '100%', padding: '8px', marginTop: '5px' }}
              />
            </div>
            <div>
              <label>Description</label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Optional description of this epic type"
                style={{ width: '100%', padding: '8px', marginTop: '5px', minHeight: '80px' }}
              />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
              <div>
                <label>Typical Min Hours</label>
                <input
                  type="number"
                  value={formData.typical_hours_min}
                  onChange={(e) => setFormData({ ...formData, typical_hours_min: e.target.value })}
                  placeholder="e.g., 50"
                  style={{ width: '100%', padding: '8px', marginTop: '5px' }}
                />
              </div>
              <div>
                <label>Typical Max Hours</label>
                <input
                  type="number"
                  value={formData.typical_hours_max}
                  onChange={(e) => setFormData({ ...formData, typical_hours_max: e.target.value })}
                  placeholder="e.g., 200"
                  style={{ width: '100%', padding: '8px', marginTop: '5px' }}
                />
              </div>
            </div>
            <button
              onClick={handleCreate}
              disabled={!formData.name}
              style={{
                background: formData.name ? '#554DFF' : '#ccc',
                color: 'white',
                border: 'none',
                padding: '10px 20px',
                borderRadius: '5px',
                cursor: formData.name ? 'pointer' : 'not-allowed'
              }}
            >
              Create Template
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div>Loading templates...</div>
      ) : (
        <DragDropContext onDragEnd={handleDragEnd}>
          <Droppable droppableId="templates">
            {(provided) => (
              <div {...provided.droppableProps} ref={provided.innerRef}>
                {templates.map((template, index) => (
                  <Draggable key={template.id} draggableId={`template-${template.id}`} index={index}>
                    {(provided) => (
                      <div
                        ref={provided.innerRef}
                        {...provided.draggableProps}
                        {...provided.dragHandleProps}
                        style={{
                          background: 'white',
                          padding: '15px',
                          marginBottom: '10px',
                          borderRadius: '8px',
                          border: '1px solid #e0e0e0',
                          ...provided.draggableProps.style
                        }}
                      >
                        {editingId === template.id ? (
                          <div>
                            {/* Edit form - similar structure to create form */}
                            <input
                              type="text"
                              defaultValue={template.name}
                              onBlur={(e) => {
                                if (e.target.value !== template.name) {
                                  handleUpdate(template.id, { name: e.target.value });
                                }
                              }}
                              style={{ width: '100%', padding: '8px', marginBottom: '10px' }}
                            />
                            <button onClick={() => setEditingId(null)}>Done</button>
                          </div>
                        ) : (
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div>
                              <h4 style={{ margin: '0 0 5px 0' }}>{template.name}</h4>
                              {template.description && (
                                <p style={{ margin: '0 0 5px 0', color: '#666' }}>{template.description}</p>
                              )}
                              {(template.typical_hours_min || template.typical_hours_max) && (
                                <p style={{ margin: 0, fontSize: '14px', color: '#888' }}>
                                  Typical: {template.typical_hours_min || '?'}h - {template.typical_hours_max || '?'}h
                                </p>
                              )}
                            </div>
                            <div style={{ display: 'flex', gap: '10px' }}>
                              <button onClick={() => setEditingId(template.id)}>Edit</button>
                              <button onClick={() => handleDelete(template.id)} style={{ color: 'red' }}>
                                Delete
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </Draggable>
                ))}
                {provided.placeholder}
              </div>
            )}
          </Droppable>
        </DragDropContext>
      )}

      {templates.length === 0 && !loading && (
        <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
          No templates yet. Click "Add Template" to create your first epic template.
        </div>
      )}
    </div>
  );
};

export default EpicTemplates;
```

**Install Dependencies**:
```bash
cd frontend
npm install react-beautiful-dnd @types/react-beautiful-dnd
```

**Add Route in `frontend/src/App.tsx`**:
```typescript
import EpicTemplates from './components/EpicTemplates';

// In Routes:
<Route path="/epic-templates" element={<EpicTemplates />} />
```

**Add Navigation Link** (in your navigation component):
```typescript
<Link to="/epic-templates">Epic Templates</Link>
```

---

### Feature 2: Project Characteristics in Project Settings

#### Backend API Updates (`src/routes/projects.py`)

**Add New Endpoints**:
```python
@projects_bp.route('/projects/<project_key>/characteristics', methods=['GET'])
@auth_required
def get_project_characteristics(user, project_key):
    """Get characteristics for a project."""
    try:
        with session_scope() as db:
            from src.models import ProjectCharacteristics

            characteristics = db.query(ProjectCharacteristics)\
                .filter_by(project_key=project_key)\
                .first()

            if characteristics:
                return jsonify({
                    'success': True,
                    'characteristics': characteristics.to_dict()
                })
            else:
                # Return defaults if not set
                return jsonify({
                    'success': True,
                    'characteristics': {
                        'project_key': project_key,
                        'be_integrations': 3,
                        'custom_theme': 3,
                        'custom_designs': 3,
                        'ux_research': 3,
                        'extensive_customizations': 3,
                        'project_oversight': 3
                    }
                })

    except Exception as e:
        logger.error(f"Failed to get characteristics for {project_key}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/projects/<project_key>/characteristics', methods=['PUT'])
@auth_required
def update_project_characteristics(user, project_key):
    """Update or create characteristics for a project."""
    try:
        data = request.json

        # Validate values are in range 1-5
        for field in ['be_integrations', 'custom_theme', 'custom_designs',
                     'ux_research', 'extensive_customizations', 'project_oversight']:
            if field in data:
                value = data[field]
                if not isinstance(value, int) or value < 1 or value > 5:
                    return jsonify({
                        'success': False,
                        'error': f'{field} must be an integer between 1 and 5'
                    }), 400

        with session_scope() as db:
            from src.models import Project, ProjectCharacteristics

            # Ensure project exists
            project = db.query(Project).filter_by(key=project_key).first()
            if not project:
                # Create project if it doesn't exist
                project = Project(key=project_key, name=project_key, is_active=True)
                db.add(project)
                db.flush()

            # Get or create characteristics
            characteristics = db.query(ProjectCharacteristics)\
                .filter_by(project_key=project_key)\
                .first()

            if not characteristics:
                characteristics = ProjectCharacteristics(project_key=project_key)
                db.add(characteristics)

            # Update fields
            for field in ['be_integrations', 'custom_theme', 'custom_designs',
                         'ux_research', 'extensive_customizations', 'project_oversight']:
                if field in data:
                    setattr(characteristics, field, data[field])

            db.flush()

            return jsonify({
                'success': True,
                'characteristics': characteristics.to_dict()
            })

    except Exception as e:
        logger.error(f"Failed to update characteristics for {project_key}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
```

#### Frontend UI Updates

**Update Projects Component** (add characteristics sliders to project edit modal/form):
```typescript
// Add to Projects.tsx or ProjectSettings.tsx

const [characteristics, setCharacteristics] = useState({
  be_integrations: 3,
  custom_theme: 3,
  custom_designs: 3,
  ux_research: 3,
  extensive_customizations: 3,
  project_oversight: 3
});

// Fetch characteristics when project is selected
useEffect(() => {
  if (selectedProject) {
    fetchCharacteristics(selectedProject.key);
  }
}, [selectedProject]);

const fetchCharacteristics = async (projectKey: string) => {
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/projects/${projectKey}/characteristics`,
      { credentials: 'include' }
    );
    const data = await response.json();
    if (data.success) {
      setCharacteristics(data.characteristics);
    }
  } catch (error) {
    console.error('Failed to fetch characteristics:', error);
  }
};

const saveCharacteristics = async () => {
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/projects/${selectedProject.key}/characteristics`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(characteristics)
      }
    );
    const data = await response.json();
    if (data.success) {
      alert('Characteristics saved successfully');
    } else {
      alert(`Error: ${data.error}`);
    }
  } catch (error) {
    console.error('Failed to save characteristics:', error);
    alert('Failed to save characteristics');
  }
};

// Slider Component (reuse from ProjectForecastTab)
const CharacteristicSlider = ({ label, value, onChange, description }: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  description: string;
}) => (
  <div style={{ marginBottom: '20px' }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
      <label style={{ fontWeight: 500 }}>{label}</label>
      <span style={{ color: '#554DFF', fontWeight: 600 }}>
        {['Minimal', 'Low', 'Moderate', 'High', 'Very High'][value - 1]}
      </span>
    </div>
    <input
      type="range"
      min="1"
      max="5"
      step="1"
      value={value}
      onChange={(e) => onChange(parseInt(e.target.value))}
      style={{ width: '100%' }}
    />
    <p style={{ fontSize: '12px', color: '#666', margin: '5px 0 0 0' }}>
      {description}
    </p>
  </div>
);

// Add to JSX:
<div className="project-characteristics-section">
  <h3>Project Characteristics (for Forecasting)</h3>
  <p style={{ color: '#666', marginBottom: '20px' }}>
    These characteristics help improve forecasting accuracy by matching similar historical projects.
  </p>

  <CharacteristicSlider
    label="Backend Integrations"
    value={characteristics.be_integrations}
    onChange={(val) => setCharacteristics({ ...characteristics, be_integrations: val })}
    description="Complexity of backend integrations (APIs, databases, external services)"
  />

  <CharacteristicSlider
    label="Custom Theme"
    value={characteristics.custom_theme}
    onChange={(val) => setCharacteristics({ ...characteristics, custom_theme: val })}
    description="Level of custom theme development needed"
  />

  <CharacteristicSlider
    label="Custom Designs"
    value={characteristics.custom_designs}
    onChange={(val) => setCharacteristics({ ...characteristics, custom_designs: val })}
    description="Amount of custom design work required"
  />

  <CharacteristicSlider
    label="UX Research"
    value={characteristics.ux_research}
    onChange={(val) => setCharacteristics({ ...characteristics, ux_research: val })}
    description="Scope of UX research activities"
  />

  <CharacteristicSlider
    label="Extensive Customizations"
    value={characteristics.extensive_customizations}
    onChange={(val) => setCharacteristics({ ...characteristics, extensive_customizations: val })}
    description="Level of custom feature development"
  />

  <CharacteristicSlider
    label="Project Oversight"
    value={characteristics.project_oversight}
    onChange={(val) => setCharacteristics({ ...characteristics, project_oversight: val })}
    description="PM oversight and coordination needs"
  />

  <button
    onClick={saveCharacteristics}
    style={{
      background: '#554DFF',
      color: 'white',
      border: 'none',
      padding: '10px 20px',
      borderRadius: '5px',
      cursor: 'pointer',
      marginTop: '10px'
    }}
  >
    Save Characteristics
  </button>
</div>
```

---

### Feature 3: Rebuild Forecasting Models Button

#### Backend Service (`src/services/analytics_runner.py`)

**Create New Service File**:
```python
"""Service for running analysis scripts to rebuild forecasting models."""
import logging
import subprocess
import os
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class AnalyticsRunner:
    """Run analysis scripts to rebuild forecasting models from production data."""

    SCRIPTS_DIR = Path(__file__).parent.parent.parent / 'scripts'
    ANALYSIS_SCRIPTS = [
        'deep_analysis_epic_hours.py',
        'epic_lifecycle_analysis.py',
        'build_forecasting_baselines.py'
    ]

    def __init__(self):
        self.scripts_dir = self.SCRIPTS_DIR

    def run_full_analysis(self) -> dict:
        """
        Run all 3 analysis scripts sequentially.

        Returns:
            dict: Results summary with success status, timing, and any errors
        """
        results = {
            'success': True,
            'started_at': datetime.utcnow().isoformat(),
            'scripts': []
        }

        for script_name in self.ANALYSIS_SCRIPTS:
            script_path = self.scripts_dir / script_name

            if not script_path.exists():
                results['scripts'].append({
                    'name': script_name,
                    'success': False,
                    'error': 'Script file not found',
                    'duration_seconds': 0
                })
                results['success'] = False
                continue

            logger.info(f"Running analysis script: {script_name}")

            try:
                start_time = datetime.utcnow()

                # Run script using Python
                result = subprocess.run(
                    ['python', str(script_path)],
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minutes max per script
                    cwd=str(script_path.parent.parent)  # Run from project root
                )

                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds()

                script_result = {
                    'name': script_name,
                    'success': result.returncode == 0,
                    'duration_seconds': duration,
                    'stdout': result.stdout[-500:] if result.stdout else '',  # Last 500 chars
                    'stderr': result.stderr[-500:] if result.stderr else ''
                }

                if result.returncode != 0:
                    script_result['error'] = f"Script exited with code {result.returncode}"
                    results['success'] = False
                    logger.error(f"{script_name} failed: {script_result['error']}")
                else:
                    logger.info(f"{script_name} completed successfully in {duration:.2f}s")

                results['scripts'].append(script_result)

            except subprocess.TimeoutExpired:
                results['scripts'].append({
                    'name': script_name,
                    'success': False,
                    'error': 'Script timed out after 5 minutes',
                    'duration_seconds': 300
                })
                results['success'] = False
                logger.error(f"{script_name} timed out")

            except Exception as e:
                results['scripts'].append({
                    'name': script_name,
                    'success': False,
                    'error': str(e),
                    'duration_seconds': 0
                })
                results['success'] = False
                logger.error(f"Failed to run {script_name}: {e}")

        results['completed_at'] = datetime.utcnow().isoformat()

        return results

    def get_analysis_output_summary(self) -> dict:
        """
        Read the latest analysis outputs and return a summary.

        Returns:
            dict: Summary of key findings from analysis results
        """
        analysis_dir = self.scripts_dir.parent / 'analysis_results'

        summary = {
            'deep_insights': {},
            'lifecycle_analysis': {},
            'forecasting_baselines': {}
        }

        try:
            # Read key CSV files and extract summary stats
            import pandas as pd

            # Deep insights summary
            baselines_file = analysis_dir / 'deep_insights' / 'epic_baseline_estimates.csv'
            if baselines_file.exists():
                df = pd.read_csv(baselines_file)
                summary['deep_insights']['epic_count'] = len(df)
                summary['deep_insights']['total_hours'] = df['median_hours'].sum() if 'median_hours' in df.columns else 0

            # Lifecycle analysis summary
            lifecycle_file = analysis_dir / 'lifecycle_analysis' / 'team_lifecycle_percentages.csv'
            if lifecycle_file.exists():
                df = pd.read_csv(lifecycle_file)
                summary['lifecycle_analysis']['teams_analyzed'] = df['team'].nunique() if 'team' in df.columns else 0

            # Forecasting baselines summary
            baselines_file = analysis_dir / 'forecasting_baselines' / 'baseline_hours_by_project_type.csv'
            if baselines_file.exists():
                df = pd.read_csv(baselines_file)
                summary['forecasting_baselines']['project_types'] = len(df)

        except Exception as e:
            logger.warning(f"Could not read analysis output summaries: {e}")

        return summary
```

#### Backend API (`src/routes/analytics.py`)

**Add New Endpoint**:
```python
from src.services.analytics_runner import AnalyticsRunner

@analytics_bp.route('/rebuild-forecasting-models', methods=['POST'])
@auth_required
def rebuild_forecasting_models(user):
    """
    Trigger a full rebuild of forecasting models from production data.

    Runs all 3 analysis scripts:
    1. deep_analysis_epic_hours.py
    2. epic_lifecycle_analysis.py
    3. build_forecasting_baselines.py
    """
    try:
        # Check if user has admin role
        if user.role.value != 'admin':
            return jsonify({
                'success': False,
                'error': 'Only admins can rebuild forecasting models'
            }), 403

        logger.info(f"User {user.email} triggered forecasting model rebuild")

        runner = AnalyticsRunner()
        results = runner.run_full_analysis()

        # Get summary of analysis outputs
        if results['success']:
            output_summary = runner.get_analysis_output_summary()
            results['output_summary'] = output_summary

        return jsonify(results)

    except Exception as e:
        logger.error(f"Failed to rebuild forecasting models: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
```

#### Frontend UI (Add to Analytics Page)

**Add Button in Analytics Component**:
```typescript
const [rebuildingModels, setRebuildingModels] = useState(false);
const [rebuildResults, setRebuildResults] = useState<any>(null);

const handleRebuildModels = async () => {
  if (!confirm(
    'This will run 3 analysis scripts and may take 2-5 minutes. Continue?'
  )) {
    return;
  }

  try {
    setRebuildingModels(true);
    setRebuildResults(null);

    const response = await fetch(
      `${API_BASE_URL}/api/analytics/rebuild-forecasting-models`,
      {
        method: 'POST',
        credentials: 'include'
      }
    );

    const data = await response.json();
    setRebuildResults(data);

    if (data.success) {
      alert('Forecasting models rebuilt successfully!');
    } else {
      alert(`Error: ${data.error || 'Failed to rebuild models'}`);
    }
  } catch (error) {
    console.error('Failed to rebuild models:', error);
    alert('Failed to rebuild forecasting models');
  } finally {
    setRebuildingModels(false);
  }
};

// JSX:
<div className="model-management-section" style={{ marginTop: '30px' }}>
  <h3>Forecasting Model Management</h3>
  <p style={{ color: '#666', marginBottom: '15px' }}>
    Rebuild forecasting models using the latest production data from epic_hours table.
    This runs all 3 analysis scripts and updates the baseline hours and lifecycle patterns.
  </p>

  <button
    onClick={handleRebuildModels}
    disabled={rebuildingModels}
    style={{
      background: rebuildingModels ? '#ccc' : '#554DFF',
      color: 'white',
      border: 'none',
      padding: '12px 24px',
      borderRadius: '5px',
      cursor: rebuildingModels ? 'not-allowed' : 'pointer',
      fontSize: '16px'
    }}
  >
    {rebuildingModels ? 'Rebuilding Models...' : 'Rebuild Forecasting Models'}
  </button>

  {rebuildResults && (
    <div style={{
      marginTop: '20px',
      padding: '15px',
      background: rebuildResults.success ? '#e8f5e9' : '#ffebee',
      borderRadius: '5px'
    }}>
      <h4>Rebuild Results:</h4>
      <ul style={{ marginTop: '10px' }}>
        {rebuildResults.scripts?.map((script: any, idx: number) => (
          <li key={idx} style={{ marginBottom: '10px' }}>
            <strong>{script.name}</strong>: {script.success ? '✅ Success' : '❌ Failed'}
            {' '}({script.duration_seconds}s)
            {script.error && (
              <div style={{ color: 'red', fontSize: '14px' }}>Error: {script.error}</div>
            )}
          </li>
        ))}
      </ul>

      {rebuildResults.output_summary && (
        <div style={{ marginTop: '15px' }}>
          <h5>Analysis Summary:</h5>
          <pre style={{ fontSize: '12px' }}>
            {JSON.stringify(rebuildResults.output_summary, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )}
</div>
```

---

### Feature 4: Epic Hours Breakdown by Month in Forecast

#### Backend Updates (`src/services/forecasting_service.py`)

**Add New Method**:
```python
def calculate_epic_schedule_breakdown(
    self,
    total_hours: int,
    start_date: date,
    duration_months: int,
    characteristics: dict,
    selected_teams: List[str]
) -> List[dict]:
    """
    Calculate epic-level breakdown by month showing hours per epic per month.

    Returns:
        List of dicts: [
            {
                'epic_name': str,
                'month_1': int,
                'month_2': int,
                ...
                'total': int
            }
        ]
    """
    # Get epic schedule from existing project-schedule logic
    # (This already returns epic breakdown by month)
    epic_schedule = self.calculate_epic_schedule(
        total_hours=total_hours,
        start_date=start_date,
        duration_months=duration_months,
        characteristics=characteristics
    )

    # Reshape data for table display
    epic_breakdown = {}

    for month_data in epic_schedule:
        month_num = month_data['month']

        for epic in month_data.get('epics', []):
            epic_name = epic['epic_name']
            hours = epic['hours']

            if epic_name not in epic_breakdown:
                epic_breakdown[epic_name] = {
                    'epic_name': epic_name,
                    'total': 0
                }

            epic_breakdown[epic_name][f'month_{month_num}'] = hours
            epic_breakdown[epic_name]['total'] += hours

    # Convert to list and sort by total hours
    result = list(epic_breakdown.values())
    result.sort(key=lambda x: x['total'], reverse=True)

    return result
```

**Add API Endpoint** (in `src/routes/forecasts.py`):
```python
@forecasts_bp.route('/epic-breakdown', methods=['POST'])
@auth_required
def get_epic_breakdown(user):
    """Get epic hours breakdown by month."""
    try:
        data = request.json

        # Validate required fields
        required = ['total_hours', 'start_date', 'duration_months', 'characteristics']
        for field in required:
            if field not in data:
                return jsonify({'success': False, 'error': f'{field} is required'}), 400

        service = ForecastingService()

        epic_breakdown = service.calculate_epic_schedule_breakdown(
            total_hours=data['total_hours'],
            start_date=datetime.fromisoformat(data['start_date']).date(),
            duration_months=data['duration_months'],
            characteristics=data['characteristics'],
            selected_teams=data.get('selected_teams', [])
        )

        return jsonify({
            'success': True,
            'epic_breakdown': epic_breakdown
        })

    except Exception as e:
        logger.error(f"Failed to calculate epic breakdown: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
```

#### Frontend Updates (`frontend/src/components/ProjectForecastTab.tsx`)

**Add State and Fetch Logic**:
```typescript
const [epicBreakdown, setEpicBreakdown] = useState<any[]>([]);

// In calculateForecast function, also fetch epic breakdown:
const calculateForecast = async () => {
  // ... existing forecast calculation ...

  // Also fetch epic breakdown
  try {
    const breakdownResponse = await fetch(
      `${API_BASE_URL}/api/forecasts/epic-breakdown`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          total_hours: totalHours,
          start_date: startDate,
          duration_months: durationMonths,
          characteristics: characteristics,
          selected_teams: selectedTeams
        })
      }
    );

    const breakdownData = await breakdownResponse.json();
    if (breakdownData.success) {
      setEpicBreakdown(breakdownData.epic_breakdown);
    }
  } catch (error) {
    console.error('Failed to fetch epic breakdown:', error);
  }
};
```

**Add JSX Section** (after monthly breakdown table):
```typescript
{epicBreakdown.length > 0 && (
  <div className="epic-breakdown-section" style={{ marginTop: '30px' }}>
    <h3>Epic Hours Breakdown by Month</h3>
    <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '15px' }}>
      <thead>
        <tr style={{ background: '#f5f5f5', borderBottom: '2px solid #ddd' }}>
          <th style={{ padding: '10px', textAlign: 'left' }}>Epic</th>
          {Array.from({ length: durationMonths }, (_, i) => (
            <th key={i} style={{ padding: '10px', textAlign: 'right' }}>
              Month {i + 1}
            </th>
          ))}
          <th style={{ padding: '10px', textAlign: 'right', fontWeight: 'bold' }}>
            Total
          </th>
        </tr>
      </thead>
      <tbody>
        {epicBreakdown.map((epic, idx) => (
          <tr key={idx} style={{ borderBottom: '1px solid #eee' }}>
            <td style={{ padding: '10px', fontWeight: 500 }}>
              {epic.epic_name}
            </td>
            {Array.from({ length: durationMonths }, (_, i) => {
              const hours = epic[`month_${i + 1}`] || 0;
              return (
                <td key={i} style={{ padding: '10px', textAlign: 'right' }}>
                  {hours > 0 ? `${hours}h` : '-'}
                </td>
              );
            })}
            <td style={{ padding: '10px', textAlign: 'right', fontWeight: 'bold' }}>
              {epic.total}h
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
)}
```

---

### Feature 5: Export Forecast Epics to Jira

#### Install Fuzzy Matching Library

```bash
# Backend
pip install fuzzywuzzy python-Levenshtein
echo "fuzzywuzzy==0.18.0" >> requirements.txt
echo "python-Levenshtein==0.21.1" >> requirements.txt
```

#### Backend Service (`src/services/jira_epic_matcher.py`)

**Create New Service File**:
```python
"""Service for matching forecast epics to Jira epics using fuzzy matching."""
import logging
from fuzzywuzzy import fuzz
from typing import List, Dict, Optional, Tuple
from src.integrations.jira_rest import JiraRestClient

logger = logging.getLogger(__name__)


class JiraEpicMatcher:
    """Match forecast epic names to existing Jira epics."""

    MATCH_THRESHOLD = 70  # Minimum similarity score to consider a match
    GOOD_MATCH_THRESHOLD = 85  # Score above which we're confident in the match

    def __init__(self, jira_client: JiraRestClient):
        self.jira_client = jira_client

    def find_matching_epics(
        self,
        project_key: str,
        forecast_epic_names: List[str]
    ) -> List[Dict]:
        """
        Find matching Jira epics for each forecast epic name.

        Args:
            project_key: Jira project key
            forecast_epic_names: List of epic names from forecast

        Returns:
            List of match results:
            [
                {
                    'forecast_name': str,
                    'matches': [
                        {
                            'jira_epic': dict (epic data),
                            'score': int (0-100),
                            'confidence': str ('high', 'medium', 'low')
                        }
                    ],
                    'recommendation': 'use_existing' | 'create_new'
                }
            ]
        """
        # Fetch all epics in project
        try:
            jira_epics = self._fetch_project_epics(project_key)
        except Exception as e:
            logger.error(f"Failed to fetch Jira epics for {project_key}: {e}")
            raise

        results = []

        for forecast_name in forecast_epic_names:
            matches = self._find_matches_for_epic(forecast_name, jira_epics)

            # Sort by score
            matches.sort(key=lambda x: x['score'], reverse=True)

            # Determine recommendation
            best_match = matches[0] if matches else None
            recommendation = 'create_new'

            if best_match and best_match['score'] >= self.GOOD_MATCH_THRESHOLD:
                recommendation = 'use_existing'

            results.append({
                'forecast_name': forecast_name,
                'matches': matches[:5],  # Top 5 matches
                'recommendation': recommendation
            })

        return results

    def _fetch_project_epics(self, project_key: str) -> List[Dict]:
        """Fetch all epics in a Jira project."""
        jql = f'project = {project_key} AND type = Epic'

        response = self.jira_client.search_issues(
            jql=jql,
            max_results=1000,
            fields=['summary', 'key', 'status', 'description']
        )

        return response.get('issues', [])

    def _find_matches_for_epic(
        self,
        forecast_name: str,
        jira_epics: List[Dict]
    ) -> List[Dict]:
        """
        Find matching Jira epics for a single forecast epic name.

        Uses multiple fuzzy matching strategies:
        1. Full string ratio
        2. Partial ratio (substring matching)
        3. Token sort ratio (word order invariant)
        """
        matches = []

        for jira_epic in jira_epics:
            jira_name = jira_epic['fields']['summary']

            # Calculate multiple similarity scores
            full_ratio = fuzz.ratio(
                forecast_name.lower(),
                jira_name.lower()
            )

            partial_ratio = fuzz.partial_ratio(
                forecast_name.lower(),
                jira_name.lower()
            )

            token_sort_ratio = fuzz.token_sort_ratio(
                forecast_name.lower(),
                jira_name.lower()
            )

            # Use max score
            best_score = max(full_ratio, partial_ratio, token_sort_ratio)

            # Only include if above threshold
            if best_score >= self.MATCH_THRESHOLD:
                confidence = 'high' if best_score >= self.GOOD_MATCH_THRESHOLD else \
                           'medium' if best_score >= 80 else 'low'

                matches.append({
                    'jira_epic': {
                        'key': jira_epic['key'],
                        'summary': jira_name,
                        'status': jira_epic['fields']['status']['name'],
                        'description': jira_epic['fields'].get('description', '')
                    },
                    'score': best_score,
                    'confidence': confidence
                })

        return matches

    def create_epic_in_jira(
        self,
        project_key: str,
        epic_name: str,
        description: Optional[str] = None,
        estimated_hours: Optional[int] = None
    ) -> Dict:
        """
        Create a new epic in Jira.

        Args:
            project_key: Jira project key
            epic_name: Epic summary/name
            description: Optional description
            estimated_hours: Optional hour estimate

        Returns:
            dict: Created epic data with key, id, summary
        """
        issue_data = {
            'fields': {
                'project': {'key': project_key},
                'summary': epic_name,
                'issuetype': {'name': 'Epic'},
                'description': description or f'Epic created from forecast: {epic_name}'
            }
        }

        # Add time estimate if provided (requires Original Estimate field)
        if estimated_hours:
            # Convert hours to seconds (Jira uses seconds internally)
            issue_data['fields']['timetracking'] = {
                'originalEstimate': f'{estimated_hours}h'
            }

        try:
            response = self.jira_client.create_issue(issue_data)

            logger.info(f"Created epic {response['key']} in {project_key}: {epic_name}")

            return {
                'key': response['key'],
                'id': response['id'],
                'summary': epic_name
            }

        except Exception as e:
            logger.error(f"Failed to create epic in Jira: {e}")
            raise
```

#### Backend API (`src/routes/jira.py`)

**Add New Endpoints**:
```python
from src.services.jira_epic_matcher import JiraEpicMatcher
from src.integrations.jira_rest import JiraRestClient

@jira_bp.route('/match-forecast-epics', methods=['POST'])
@auth_required
def match_forecast_epics(user):
    """
    Find matching Jira epics for forecast epic names using fuzzy matching.

    Request body:
    {
        "project_key": "PROJ",
        "forecast_epic_names": ["Discovery", "Design System", ...]
    }
    """
    try:
        data = request.json

        project_key = data.get('project_key')
        forecast_epic_names = data.get('forecast_epic_names', [])

        if not project_key or not forecast_epic_names:
            return jsonify({
                'success': False,
                'error': 'project_key and forecast_epic_names required'
            }), 400

        jira_client = JiraRestClient()
        matcher = JiraEpicMatcher(jira_client)

        matches = matcher.find_matching_epics(project_key, forecast_epic_names)

        return jsonify({
            'success': True,
            'matches': matches
        })

    except Exception as e:
        logger.error(f"Failed to match forecast epics: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@jira_bp.route('/create-forecast-epics', methods=['POST'])
@auth_required
def create_forecast_epics(user):
    """
    Create epics in Jira from forecast data.

    Request body:
    {
        "project_key": "PROJ",
        "epics": [
            {
                "name": "Discovery",
                "action": "create" | "use_existing",
                "existing_key": "PROJ-123" (if use_existing),
                "estimated_hours": 100
            }
        ]
    }
    """
    try:
        data = request.json

        project_key = data.get('project_key')
        epics = data.get('epics', [])

        if not project_key or not epics:
            return jsonify({
                'success': False,
                'error': 'project_key and epics required'
            }), 400

        jira_client = JiraRestClient()
        matcher = JiraEpicMatcher(jira_client)

        results = []

        for epic_data in epics:
            action = epic_data.get('action')

            if action == 'create':
                # Create new epic
                created_epic = matcher.create_epic_in_jira(
                    project_key=project_key,
                    epic_name=epic_data['name'],
                    description=epic_data.get('description'),
                    estimated_hours=epic_data.get('estimated_hours')
                )

                results.append({
                    'name': epic_data['name'],
                    'action': 'created',
                    'epic_key': created_epic['key'],
                    'success': True
                })

            elif action == 'use_existing':
                # Link to existing epic
                existing_key = epic_data.get('existing_key')

                if not existing_key:
                    results.append({
                        'name': epic_data['name'],
                        'action': 'skipped',
                        'error': 'No existing_key provided',
                        'success': False
                    })
                    continue

                results.append({
                    'name': epic_data['name'],
                    'action': 'linked',
                    'epic_key': existing_key,
                    'success': True
                })

            else:
                results.append({
                    'name': epic_data['name'],
                    'action': 'skipped',
                    'error': f'Unknown action: {action}',
                    'success': False
                })

        return jsonify({
            'success': True,
            'results': results
        })

    except Exception as e:
        logger.error(f"Failed to create forecast epics: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
```

#### Frontend Modal (`frontend/src/components/ExportEpicsModal.tsx`)

**Create Modal Component**:
```typescript
// (Due to length, this is a simplified version - full implementation would be ~300 lines)

import React, { useState, useEffect } from 'react';

interface ExportEpicsModalProps {
  isOpen: boolean;
  onClose: () => void;
  forecastData: any;
  projectKey: string;
}

const ExportEpicsModal: React.FC<ExportEpicsModalProps> = ({
  isOpen,
  onClose,
  forecastData,
  projectKey
}) => {
  const [step, setStep] = useState<'matching' | 'review' | 'creating' | 'done'>('matching');
  const [matches, setMatches] = useState<any[]>([]);
  const [epicMappings, setEpicMappings] = useState<any[]>([]);
  const [createResults, setCreateResults] = useState<any[]>([]);

  useEffect(() => {
    if (isOpen && step === 'matching') {
      performMatching();
    }
  }, [isOpen]);

  const performMatching = async () => {
    // Extract epic names from forecast
    const epicNames = forecastData.epic_schedule
      .flatMap((month: any) => month.epics.map((e: any) => e.epic_name))
      .filter((name: string, idx: number, self: string[]) => self.indexOf(name) === idx);

    try {
      const response = await fetch(`${API_BASE_URL}/api/jira/match-forecast-epics`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          project_key: projectKey,
          forecast_epic_names: epicNames
        })
      });

      const data = await response.json();

      if (data.success) {
        setMatches(data.matches);

        // Initialize epic mappings with recommendations
        const mappings = data.matches.map((match: any) => ({
          name: match.forecast_name,
          action: match.recommendation === 'use_existing' ? 'use_existing' : 'create',
          existing_key: match.matches[0]?.jira_epic?.key || null,
          estimated_hours: calculateEpicHours(match.forecast_name)
        }));

        setEpicMappings(mappings);
        setStep('review');
      }
    } catch (error) {
      console.error('Matching failed:', error);
      alert('Failed to match epics');
    }
  };

  const calculateEpicHours = (epicName: string): number => {
    return forecastData.epic_schedule.reduce((total: number, month: any) => {
      const epic = month.epics.find((e: any) => e.epic_name === epicName);
      return total + (epic?.hours || 0);
    }, 0);
  };

  const handleCreateEpics = async () => {
    setStep('creating');

    try {
      const response = await fetch(`${API_BASE_URL}/api/jira/create-forecast-epics`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          project_key: projectKey,
          epics: epicMappings
        })
      });

      const data = await response.json();

      if (data.success) {
        setCreateResults(data.results);
        setStep('done');
      }
    } catch (error) {
      console.error('Creation failed:', error);
      alert('Failed to create epics');
      setStep('review');
    }
  };

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0,0,0,0.5)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000
    }}>
      <div style={{
        background: 'white',
        padding: '30px',
        borderRadius: '10px',
        maxWidth: '800px',
        width: '90%',
        maxHeight: '80vh',
        overflow: 'auto'
      }}>
        <h2>Export Forecast Epics to Jira</h2>

        {step === 'matching' && (
          <div>Matching forecast epics to existing Jira epics...</div>
        )}

        {step === 'review' && (
          <div>
            <p>Review and adjust epic mappings:</p>
            {/* Render epic mapping table with action dropdowns */}
            <button onClick={handleCreateEpics}>Create Epics in Jira</button>
          </div>
        )}

        {step === 'creating' && (
          <div>Creating epics in Jira...</div>
        )}

        {step === 'done' && (
          <div>
            <h3>Results:</h3>
            {/* Render creation results */}
            <button onClick={onClose}>Close</button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ExportEpicsModal;
```

**Add to ProjectForecastTab**:
```typescript
import ExportEpicsModal from './ExportEpicsModal';

const [showExportModal, setShowExportModal] = useState(false);

// Add button after forecast is generated:
<button
  onClick={() => setShowExportModal(true)}
  style={{
    background: '#00FFCE',
    color: '#000',
    border: 'none',
    padding: '12px 24px',
    borderRadius: '5px',
    cursor: 'pointer',
    marginTop: '20px'
  }}
>
  Export to Jira
</button>

<ExportEpicsModal
  isOpen={showExportModal}
  onClose={() => setShowExportModal(false)}
  forecastData={forecastResult}
  projectKey={selectedProject}
/>
```

---

## Testing Checklist

### Feature 1: Epic Templates
- [ ] Create new template via UI
- [ ] Edit template name and hours
- [ ] Delete template
- [ ] Drag and drop to reorder
- [ ] Verify persistence after page reload

### Feature 2: Project Characteristics
- [ ] Set characteristics for historical project (e.g., SRLK)
- [ ] Verify sliders save correctly
- [ ] Check characteristics load on project selection

### Feature 3: Rebuild Models
- [ ] Click rebuild button (admin user)
- [ ] Verify all 3 scripts run successfully
- [ ] Check analysis_results/ directory for updated CSVs
- [ ] Verify forecasts reflect updated baselines

### Feature 4: Epic Breakdown
- [ ] Generate forecast
- [ ] Verify epic hours by month table appears
- [ ] Check totals match forecast
- [ ] Test with different duration_months values

### Feature 5: Export to Jira
- [ ] Generate forecast
- [ ] Click "Export to Jira"
- [ ] Verify fuzzy matching finds existing epics
- [ ] Test creating new epics
- [ ] Test linking to existing epics
- [ ] Check Jira for created epics with estimates

---

## Deployment Steps

1. **Database Migration**:
   ```bash
   alembic upgrade head
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   cd frontend && npm install
   ```

3. **Seed Initial Epic Templates** (optional):
   ```python
   # scripts/seed_epic_templates.py
   from src.models import StandardEpicTemplate
   from src.utils.database import session_scope

   templates = [
       {"name": "Discovery", "order": 1, "typical_hours_min": 50, "typical_hours_max": 150},
       {"name": "Design System", "order": 2, "typical_hours_min": 100, "typical_hours_max": 300},
       {"name": "Frontend Build", "order": 3, "typical_hours_min": 200, "typical_hours_max": 600},
       {"name": "Backend API", "order": 4, "typical_hours_min": 150, "typical_hours_max": 500},
       # Add more...
   ]

   with session_scope() as db:
       for t in templates:
           template = StandardEpicTemplate(**t)
           db.add(template)
   ```

4. **Run Build**:
   ```bash
   cd frontend && npm run build
   ```

5. **Deploy to Production**:
   ```bash
   git add .
   git commit -m "feat: Add epic analysis and forecasting enhancements"
   git push origin main
   # DigitalOcean will auto-deploy
   ```

---

## File Structure Summary

**New Files Created**:
- `src/models/project.py`
- `src/models/standard_epic_template.py`
- `src/routes/epic_templates.py`
- `src/services/analytics_runner.py`
- `src/services/jira_epic_matcher.py`
- `frontend/src/components/EpicTemplates.tsx`
- `frontend/src/components/ExportEpicsModal.tsx`
- `docs/EPIC_FORECASTING_IMPLEMENTATION_PLAN.md`

**Modified Files**:
- `src/models/__init__.py`
- `src/routes/projects.py`
- `src/routes/analytics.py`
- `src/routes/jira.py`
- `src/routes/forecasts.py`
- `src/services/forecasting_service.py`
- `frontend/src/components/ProjectForecastTab.tsx`
- `frontend/src/App.tsx`
- `requirements.txt`
- `frontend/package.json`

---

## Next Steps

1. Complete remaining implementation from this plan
2. Test each feature thoroughly
3. Update analysis scripts to use project_characteristics
4. Document API endpoints in OpenAPI/Swagger
5. Add user permissions (admin-only for model rebuild)
6. Consider background jobs for long-running analysis

---

**End of Implementation Plan**
