import { fetchUser, type User } from "@/client";
import { z } from "zod";

export const LIMIT = 3;

export function serve(id: string): User { return fetchUser(z.string().parse(id)); }
