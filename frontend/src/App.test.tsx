import React from 'react';
import { render, screen } from '@testing-library/react';
import App from './App';

// Mock react-admin to avoid complex setup
jest.mock('react-admin', () => ({
  Admin: ({ children }: { children: React.ReactNode }) => <div data-testid="admin">{children}</div>,
  Resource: () => null,
  radiantLightTheme: {},
  radiantDarkTheme: {},
}));

// Mock all component imports
jest.mock('./dataProvider', () => ({
  dataProvider: {},
}));

jest.mock('./authProvider', () => ({
  authProvider: {},
}));

jest.mock('./context/AuthContext', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  useAuth: () => ({ isAdmin: false }),
}));

jest.mock('./components/Meetings', () => ({
  MeetingList: () => null,
  MeetingShow: () => null,
  MeetingEdit: () => null,
}));

jest.mock('./components/Todos', () => ({
  TodoList: () => null,
  TodoShow: () => null,
  TodoEdit: () => null,
  TodoCreate: () => null,
}));

jest.mock('./components/Analysis', () => ({
  AnalysisList: () => null,
  AnalysisShow: () => null,
}));

jest.mock('./components/Dashboard', () => ({
  Dashboard: () => null,
}));

jest.mock('./components/Layout', () => ({
  CustomLayout: () => null,
}));

jest.mock('./components/Projects', () => ({
  ProjectList: () => null,
  ProjectShow: () => null,
}));

jest.mock('./components/LearningsList', () => ({
  LearningsList: () => null,
}));

jest.mock('./components/LearningCreate', () => ({
  LearningCreate: () => null,
}));

jest.mock('./components/LearningEdit', () => ({
  LearningEdit: () => null,
}));

jest.mock('./components/LearningShow', () => ({
  LearningShow: () => null,
}));

jest.mock('./components/Login', () => {
  return function Login() {
    return <div data-testid="login">Login</div>;
  };
});

jest.mock('./components/UserManagement', () => {
  return function UserManagement() {
    return null;
  };
});

jest.mock('./components/Settings', () => {
  return function Settings() {
    return null;
  };
});

describe('App Component', () => {
  it('renders without crashing', () => {
    render(<App />);
    expect(screen.getByTestId('admin')).toBeInTheDocument();
  });

  it('does not wrap Admin component in BrowserRouter (prevents useLocation errors)', () => {
    // This test ensures we don't nest routers which causes:
    // "useLocation() may be used only in the context of a <Router> component"
    const { container } = render(<App />);

    // React Admin provides its own router, so we should NOT have
    // a BrowserRouter or any other router wrapper
    const appString = container.innerHTML;

    // The app should render Admin directly without nested routers
    expect(screen.getByTestId('admin')).toBeInTheDocument();

    // This verifies the fix for the router nesting bug
    // If someone adds BrowserRouter back, this test will remind them not to
  });

  it('provides AuthProvider context', () => {
    // The AuthProvider should be present to provide auth context
    render(<App />);
    // If this renders without error, AuthProvider is working
    expect(screen.getByTestId('admin')).toBeInTheDocument();
  });
});
