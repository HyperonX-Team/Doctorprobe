// Application router. Routes outside the user session redirect to
// /welcome; everything else is wrapped in the authenticated layout.

import {
  createBrowserRouter,
  Navigate,
  Outlet,
  RouterProvider,
} from 'react-router-dom';
import { UserProvider, useUserContext } from './context/UserContext';
import Layout from './components/layout/Layout';
import Welcome from './pages/Welcome';
import Home from './pages/Home';
import Checkup from './pages/Checkup';
import Report from './pages/Report';
import History from './pages/History';
import Vault from './pages/Vault';
import Settings from './pages/Settings';
import LoadingSpinner from './components/ui/LoadingSpinner';

/** Redirect to /welcome when there is no active user session. */
function RequireAuth() {
  const { user, loading } = useUserContext();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <LoadingSpinner label="Restoring your session…" />
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/welcome" replace />;
  }
  return <Outlet />;
}

/** Redirect signed-in users away from the welcome page. */
function RedirectIfAuthed() {
  const { user, loading } = useUserContext();
  if (loading) {
    return null;
  }
  if (user) {
    return <Navigate to="/" replace />;
  }
  return <Welcome />;
}

const router = createBrowserRouter([
  {
    path: '/welcome',
    element: <RedirectIfAuthed />,
  },
  {
    element: <RequireAuth />,
    children: [
      {
        path: '/',
        element: <Layout />,
        children: [
          { index: true, element: <Home /> },
          { path: 'checkup', element: <Checkup /> },
          { path: 'report/:checkupId', element: <Report /> },
          { path: 'history', element: <History /> },
          { path: 'vault', element: <Vault /> },
          { path: 'settings', element: <Settings /> },
        ],
      },
    ],
  },
  {
    path: '*',
    element: <Navigate to="/" replace />,
  },
]);

export default function App() {
  return (
    <UserProvider>
      <RouterProvider router={router} />
    </UserProvider>
  );
}
