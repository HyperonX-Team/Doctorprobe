// useUser hook — typed accessor for the user session context.

import { useUserContext } from '../context/UserContext';

export function useUser() {
  return useUserContext();
}
