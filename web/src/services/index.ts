import { apiServices } from "./api";
import { mockServices } from "./mock";
import { supabaseServices } from "./supabase";

export const services = import.meta.env.VITE_DATA_MODE === "supabase"
  ? supabaseServices
  : import.meta.env.VITE_DATA_MODE === "api"
    ? apiServices
    : mockServices;
