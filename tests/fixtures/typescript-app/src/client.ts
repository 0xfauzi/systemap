export interface User { id: string }

export function fetchUser(id: string): User { return { id }; }
