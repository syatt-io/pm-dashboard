import React from 'react';
import { Admin, Resource } from 'react-admin';
import { dataProvider } from './dataProvider';
import { authProvider } from './authProvider';
import { AuthProvider, useAuth } from './context/AuthContext';
import { customLightTheme } from './theme';

// NOTE: React Admin provides its own router - do NOT wrap in BrowserRouter!

// Icons
import TaskIcon from '@mui/icons-material/Task';
import SettingsIcon from '@mui/icons-material/Settings';
import BusinessIcon from '@mui/icons-material/Business';
import FavoriteIcon from '@mui/icons-material/Favorite';
import LightbulbIcon from '@mui/icons-material/Lightbulb';
import FeedbackIcon from '@mui/icons-material/Feedback';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import CategoryIcon from '@mui/icons-material/Category';

// Components
import { MeetingShow, MeetingEdit } from './components/Meetings';
import { TodoList, TodoShow, TodoEdit, TodoCreate } from './components/Todos';
import { AnalysisList, AnalysisShow } from './components/Analysis';
import { AnalyticsList } from './components/Analytics';
import { Dashboard } from './components/Dashboard';
import { CustomLayout } from './components/Layout';
import { ProjectList, ProjectShow, ProjectEdit } from './components/Projects';
import { LearningsList } from './components/LearningsList';
import { LearningCreate } from './components/LearningCreate';
import { LearningEdit } from './components/LearningEdit';
import { LearningShow } from './components/LearningShow';
import { FeedbackList } from './components/FeedbackList';
import { FeedbackCreate } from './components/FeedbackCreate';
import { FeedbackEdit } from './components/FeedbackEdit';
import Login from './components/Login';
import Settings from './components/Settings';
import EpicTemplates from './components/EpicTemplates';

const AdminApp = () => {
  return (
    <Admin
      dataProvider={dataProvider}
      authProvider={authProvider}
      dashboard={Dashboard}
      title="PM Command Center"
      layout={CustomLayout}
      theme={customLightTheme}
      loginPage={Login}
      requireAuth
      disableTelemetry
    >
        <Resource
          name="projects"
          list={ProjectList}
          show={ProjectShow}
          edit={ProjectEdit}
          icon={BusinessIcon}
          options={{ label: 'My Projects' }}
        />
        <Resource
          name="analysis"
          list={AnalysisList}
          show={AnalysisShow}
          icon={FavoriteIcon}
          options={{ label: 'My Meetings' }}
        />
        <Resource
          name="todos"
          list={TodoList}
          show={TodoShow}
          edit={TodoEdit}
          create={TodoCreate}
          icon={TaskIcon}
          options={{ label: 'My TODOs' }}
        />
        <Resource
          name="feedback"
          list={FeedbackList}
          create={FeedbackCreate}
          edit={FeedbackEdit}
          icon={FeedbackIcon}
          options={{ label: 'My Feedback' }}
        />
        <Resource
          name="learnings"
          list={LearningsList}
          show={LearningShow}
          create={LearningCreate}
          edit={LearningEdit}
          icon={LightbulbIcon}
          options={{ label: 'Team Learnings' }}
        />
        <Resource
          name="analytics"
          list={AnalyticsList}
          icon={AnalyticsIcon}
          options={{ label: 'Analytics' }}
        />
        <Resource
          name="epic-templates"
          list={EpicTemplates}
          icon={CategoryIcon}
          options={{ label: 'Epic Templates' }}
        />
        <Resource
          name="settings"
          list={Settings}
          icon={SettingsIcon}
          options={{ label: 'Settings' }}
        />
        {/* Meetings resource hidden from nav - accessible via Analysis tabs */}
        <Resource
          name="meetings"
          show={MeetingShow}
          edit={MeetingEdit}
        />
      </Admin>
  );
};

function App() {
  // Fixed: No BrowserRouter wrapper - React Admin has its own router
  return (
    <AuthProvider>
      <AdminApp />
    </AuthProvider>
  );
}

export default App;
