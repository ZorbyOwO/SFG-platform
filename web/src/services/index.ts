import { apiServices } from "./api";
import { mockServices } from "./mock";

export const services = import.meta.env.VITE_DATA_MODE === "api" ? apiServices : mockServices;
