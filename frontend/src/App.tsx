import React from 'react';
import { Admin, Resource, radiantLightTheme, radiantDarkTheme } from 'react-admin';
import { dataProvider } from './dataProvider';
import { authProvider } from './authProvider';
import { AuthProvider, useAuth } from './context/AuthContext';

// NOTE: React Admin provides its own router - do NOT wrap in BrowserRouter!

// Icons
import MeetingRoomIcon from '@mui/icons-material/MeetingRoom';
import TaskIcon from '@mui/icons-material/Task';
import SettingsIcon from '@mui/icons-material/Settings';
import BusinessIcon from '@mui/icons-material/Business';
import FavoriteIcon from '@mui/icons-material/Favorite';
import PeopleIcon from '@mui/icons-material/People';
import LightbulbIcon from '@mui/icons-material/Lightbulb';

// Components
import { MeetingList, MeetingShow, MeetingEdit } from './components/Meetings';
import { TodoList, TodoShow, TodoEdit, TodoCreate } from './components/Todos';
import { AnalysisList, AnalysisShow } from './components/Analysis';
import { Dashboard } from './components/Dashboard';
import { CustomLayout } from './components/Layout';
import { ProjectList, ProjectShow } from './components/Projects';
import { LearningsList } from './components/LearningsList';
import { LearningCreate } from './components/LearningCreate';
import { LearningEdit } from './components/LearningEdit';
import { LearningShow } from './components/LearningShow';
import Login from './components/Login';
import UserManagement from './components/UserManagement';
import Settings from './components/Settings';

const AdminApp = () => {
  const { isAdmin } = useAuth();

  return (
    <Admin
      dataProvider={dataProvider}
      authProvider={authProvider}
      dashboard={Dashboard}
      title="PM Command Center"
      layout={CustomLayout}
      theme={radiantLightTheme}
      darkTheme={radiantDarkTheme}
      loginPage={Login}
      requireAuth
    >
        <Resource
          name="analysis"
          list={AnalysisList}
          show={AnalysisShow}
          icon={FavoriteIcon}
          options={{ label: 'Meeting Analysis' }}
        />
        <Resource
          name="meetings"
          list={MeetingList}
          show={MeetingShow}
          edit={MeetingEdit}
          icon={MeetingRoomIcon}
          options={{ label: 'All Meetings' }}
        />
        <Resource
          name="todos"
          list={TodoList}
          show={TodoShow}
          edit={TodoEdit}
          create={TodoCreate}
          icon={TaskIcon}
        />
        <Resource
          name="projects"
          list={ProjectList}
          show={ProjectShow}
          icon={BusinessIcon}
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
        {isAdmin && (
          <Resource
            name="users"
            list={UserManagement}
            icon={PeopleIcon}
            options={{ label: 'User Management' }}
          />
        )}
        <Resource
          name="settings"
          list={Settings}
          icon={SettingsIcon}
          options={{ label: 'Settings' }}
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
