import { createClient } from "npm:@supabase/supabase-js@2.112.3";

const DEFAULT_APP_ORIGINS = ["http://127.0.0.1:5500", "http://localhost:5500"];

type RegistrationBody = {
  ic?: unknown;
  full_name?: unknown;
  email?: unknown;
  password?: unknown;
  password_confirm?: unknown;
};

function allowedOrigins(): Set<string> {
  const configured = (Deno.env.get("PUBLIC_APP_URL") ?? "")
    .split(",")
    .map((origin) => origin.trim())
    .filter(Boolean);
  return new Set([...DEFAULT_APP_ORIGINS, ...configured]);
}

function responseHeaders(origin: string | null): HeadersInit {
  const allowed = allowedOrigins();
  const selected = origin && allowed.has(origin) ? origin : DEFAULT_APP_ORIGINS[0];
  return {
    "Access-Control-Allow-Origin": selected,
    "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Content-Type": "application/json",
    "Vary": "Origin",
  };
}

function jsonResponse(origin: string | null, status: number, payload: Record<string, unknown>): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: responseHeaders(origin),
  });
}

async function sha256(value: string): Promise<string> {
  const encoded = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", encoded);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function internalIdentityEmail(ic: string): string {
  return `ic-${ic}@login.sfg.example`;
}

Deno.serve(async (request: Request): Promise<Response> => {
  const origin = request.headers.get("origin");
  const origins = allowedOrigins();

  if (origin && !origins.has(origin)) {
    return jsonResponse(null, 403, { message: "This application origin is not allowed." });
  }
  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: responseHeaders(origin) });
  }
  if (request.method !== "POST") {
    return jsonResponse(origin, 405, { message: "Method not allowed." });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!supabaseUrl || !serviceRoleKey) {
    return jsonResponse(origin, 503, { message: "Registration is temporarily unavailable." });
  }

  let body: RegistrationBody;
  try {
    const rawBody = await request.text();
    if (rawBody.length > 10_000) {
      return jsonResponse(origin, 413, { message: "Registration request is too large." });
    }
    body = JSON.parse(rawBody) as RegistrationBody;
  } catch {
    return jsonResponse(origin, 400, { message: "Enter valid registration details." });
  }

  const ic = typeof body.ic === "string" ? body.ic.replace(/\D/g, "") : "";
  const fullName = typeof body.full_name === "string" ? body.full_name.trim() : "";
  const email = typeof body.email === "string" ? body.email.trim().toLowerCase() : "";
  const password = typeof body.password === "string" ? body.password : "";
  const passwordConfirm = typeof body.password_confirm === "string" ? body.password_confirm : "";

  if (ic.length !== 12) {
    return jsonResponse(origin, 422, { message: "Enter a valid 12-digit IC number." });
  }
  if (fullName.length < 2 || fullName.length > 120) {
    return jsonResponse(origin, 422, { message: "Enter your full legal name." });
  }
  if (email.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return jsonResponse(origin, 422, { message: "Enter a valid email address." });
  }
  if (password.length < 8 || password.length > 72) {
    return jsonResponse(origin, 422, { message: "Use a password between 8 and 72 characters." });
  }
  if (password !== passwordConfirm) {
    return jsonResponse(origin, 422, { message: "The password confirmation does not match." });
  }

  const client = createClient(supabaseUrl, serviceRoleKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
  const forwardedFor = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "unknown";
  const identifierHash = await sha256(`sfg-registration:${forwardedFor}`);
  const { data: withinLimit, error: limitError } = await client.rpc(
    "sfg_registration_rate_limit",
    { p_identifier_hash: identifierHash },
  );
  if (limitError || withinLimit !== true) {
    return jsonResponse(origin, 429, { message: "Too many registration attempts. Try again later." });
  }

  const [{ data: icRows, error: icError }, { data: emailRows, error: emailError }] = await Promise.all([
    client.from("profiles").select("id").eq("ic_number", ic).limit(1),
    client.from("profiles").select("id").eq("email", email).limit(1),
  ]);
  if (icError || emailError) {
    return jsonResponse(origin, 503, { message: "Registration is temporarily unavailable." });
  }
  if ((icRows?.length ?? 0) > 0 || (emailRows?.length ?? 0) > 0) {
    return jsonResponse(origin, 409, { message: "An account already uses that IC number or email." });
  }

  const { data: authData, error: authError } = await client.auth.admin.createUser({
    email: internalIdentityEmail(ic),
    password,
    email_confirm: true,
    user_metadata: { display_name: fullName },
  });
  if (authError || !authData.user) {
    const status = authError?.message.toLowerCase().includes("already") ? 409 : 503;
    const message = status === 409
      ? "An account already uses that IC number or email."
      : "Registration is temporarily unavailable.";
    return jsonResponse(origin, status, { message });
  }

  const { error: profileError } = await client.from("profiles").insert({
    id: authData.user.id,
    ic_number: ic,
    full_name: fullName,
    email,
  });
  if (profileError) {
    await client.auth.admin.deleteUser(authData.user.id);
    const status = profileError.code === "23505" ? 409 : 503;
    const message = status === 409
      ? "An account already uses that IC number or email."
      : "Registration is temporarily unavailable.";
    return jsonResponse(origin, status, { message });
  }

  return jsonResponse(origin, 201, {
    citizen_id: authData.user.id,
    enrolment_status: "ENROLMENT_STARTED",
    next_step: "face_enrolment",
  });
});
