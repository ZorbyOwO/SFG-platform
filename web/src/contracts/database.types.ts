export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.15"
  }
  public: {
    Tables: {
      audit_log: {
        Row: {
          audit_event_id: string
          audit_event_type: string
          authorization_status: string | null
          citizen_id: string | null
          correlation_id: string | null
          created_at: string
          detail: Json
          kiosk_id: string | null
          service_access_status: string | null
          session_id: string | null
          verification_completed_at: string | null
        }
        Insert: {
          audit_event_id?: string
          audit_event_type: string
          authorization_status?: string | null
          citizen_id?: string | null
          correlation_id?: string | null
          created_at?: string
          detail?: Json
          kiosk_id?: string | null
          service_access_status?: string | null
          session_id?: string | null
          verification_completed_at?: string | null
        }
        Update: {
          audit_event_id?: string
          audit_event_type?: string
          authorization_status?: string | null
          citizen_id?: string | null
          correlation_id?: string | null
          created_at?: string
          detail?: Json
          kiosk_id?: string | null
          service_access_status?: string | null
          session_id?: string | null
          verification_completed_at?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "audit_log_citizen_id_fkey"
            columns: ["citizen_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "audit_log_kiosk_id_fkey"
            columns: ["kiosk_id"]
            isOneToOne: false
            referencedRelation: "kiosks"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "audit_log_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "verification_sessions"
            referencedColumns: ["session_id"]
          },
        ]
      }
      face_templates: {
        Row: {
          capture_pose: string
          created_at: string
          embedding: string
          family_member_id: string | null
          id: string
          model_version: string
          quality_score: number | null
          template_status: string
          user_id: string
        }
        Insert: {
          capture_pose: string
          created_at?: string
          embedding: string
          family_member_id?: string | null
          id?: string
          model_version?: string
          quality_score?: number | null
          template_status?: string
          user_id: string
        }
        Update: {
          capture_pose?: string
          created_at?: string
          embedding?: string
          family_member_id?: string | null
          id?: string
          model_version?: string
          quality_score?: number | null
          template_status?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "face_templates_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "template_family_owner"
            columns: ["user_id", "family_member_id"]
            isOneToOne: false
            referencedRelation: "family_members"
            referencedColumns: ["user_id", "id"]
          },
        ]
      }
      family_members: {
        Row: {
          consent_status: string
          created_at: string
          enrolment_status: string
          full_name: string
          ic_number: string
          id: string
          idempotency_key: string | null
          profile_state: string
          relationship: string
          updated_at: string
          user_id: string
        }
        Insert: {
          consent_status?: string
          created_at?: string
          enrolment_status?: string
          full_name: string
          ic_number: string
          id?: string
          idempotency_key?: string | null
          profile_state?: string
          relationship: string
          updated_at?: string
          user_id: string
        }
        Update: {
          consent_status?: string
          created_at?: string
          enrolment_status?: string
          full_name?: string
          ic_number?: string
          id?: string
          idempotency_key?: string | null
          profile_state?: string
          relationship?: string
          updated_at?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "family_members_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      kiosks: {
        Row: {
          api_key_hash: string
          created_at: string
          id: string
          is_active: boolean
          kiosk_name: string
          merchant_location: string | null
          merchant_name: string
        }
        Insert: {
          api_key_hash: string
          created_at?: string
          id: string
          is_active?: boolean
          kiosk_name: string
          merchant_location?: string | null
          merchant_name: string
        }
        Update: {
          api_key_hash?: string
          created_at?: string
          id?: string
          is_active?: boolean
          kiosk_name?: string
          merchant_location?: string | null
          merchant_name?: string
        }
        Relationships: []
      }
      profiles: {
        Row: {
          consent_status: string
          created_at: string
          email: string
          enrolment_status: string
          full_name: string
          ic_number: string
          id: string
          pin_hash: string | null
          profile_state: string
          updated_at: string
        }
        Insert: {
          consent_status?: string
          created_at?: string
          email: string
          enrolment_status?: string
          full_name: string
          ic_number: string
          id: string
          pin_hash?: string | null
          profile_state?: string
          updated_at?: string
        }
        Update: {
          consent_status?: string
          created_at?: string
          email?: string
          enrolment_status?: string
          full_name?: string
          ic_number?: string
          id?: string
          pin_hash?: string | null
          profile_state?: string
          updated_at?: string
        }
        Relationships: []
      }
      transactions: {
        Row: {
          amount: number
          auth_method: string
          balance_after: number | null
          correlation_id: string | null
          created_at: string
          family_member_id: string | null
          id: string
          idempotency_key: string | null
          kiosk_id: string | null
          merchant_name: string | null
          reference: string
          reverses_transaction_id: string | null
          status: string
          type: string
          user_id: string | null
          wallet_id: string | null
        }
        Insert: {
          amount: number
          auth_method: string
          balance_after?: number | null
          correlation_id?: string | null
          created_at?: string
          family_member_id?: string | null
          id?: string
          idempotency_key?: string | null
          kiosk_id?: string | null
          merchant_name?: string | null
          reference: string
          reverses_transaction_id?: string | null
          status?: string
          type: string
          user_id?: string | null
          wallet_id?: string | null
        }
        Update: {
          amount?: number
          auth_method?: string
          balance_after?: number | null
          correlation_id?: string | null
          created_at?: string
          family_member_id?: string | null
          id?: string
          idempotency_key?: string | null
          kiosk_id?: string | null
          merchant_name?: string | null
          reference?: string
          reverses_transaction_id?: string | null
          status?: string
          type?: string
          user_id?: string | null
          wallet_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "transactions_family_member_id_fkey"
            columns: ["family_member_id"]
            isOneToOne: false
            referencedRelation: "family_members"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "transactions_kiosk_id_fkey"
            columns: ["kiosk_id"]
            isOneToOne: false
            referencedRelation: "kiosks"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "transactions_reverses_transaction_id_fkey"
            columns: ["reverses_transaction_id"]
            isOneToOne: false
            referencedRelation: "transactions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "transactions_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "transactions_wallet_id_fkey"
            columns: ["wallet_id"]
            isOneToOne: false
            referencedRelation: "wallets"
            referencedColumns: ["id"]
          },
        ]
      }
      verification_sessions: {
        Row: {
          amount: number | null
          authorization_status: string | null
          capture_status: string | null
          correlation_id: string
          created_at: string
          expires_at: string
          identity_confirmation_status: string | null
          kiosk_id: string | null
          liveness_status: string | null
          match_status: string | null
          matched_family_member: string | null
          matched_user: string | null
          nonce: string
          pin_attempts: number
          pin_status: string | null
          purpose: string
          service_access_status: string | null
          session_id: string
          status: string
          verification_completed_at: string | null
        }
        Insert: {
          amount?: number | null
          authorization_status?: string | null
          capture_status?: string | null
          correlation_id?: string
          created_at?: string
          expires_at?: string
          identity_confirmation_status?: string | null
          kiosk_id?: string | null
          liveness_status?: string | null
          match_status?: string | null
          matched_family_member?: string | null
          matched_user?: string | null
          nonce: string
          pin_attempts?: number
          pin_status?: string | null
          purpose: string
          service_access_status?: string | null
          session_id?: string
          status?: string
          verification_completed_at?: string | null
        }
        Update: {
          amount?: number | null
          authorization_status?: string | null
          capture_status?: string | null
          correlation_id?: string
          created_at?: string
          expires_at?: string
          identity_confirmation_status?: string | null
          kiosk_id?: string | null
          liveness_status?: string | null
          match_status?: string | null
          matched_family_member?: string | null
          matched_user?: string | null
          nonce?: string
          pin_attempts?: number
          pin_status?: string | null
          purpose?: string
          service_access_status?: string | null
          session_id?: string
          status?: string
          verification_completed_at?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "session_family_owner"
            columns: ["matched_user", "matched_family_member"]
            isOneToOne: false
            referencedRelation: "family_members"
            referencedColumns: ["user_id", "id"]
          },
          {
            foreignKeyName: "verification_sessions_kiosk_id_fkey"
            columns: ["kiosk_id"]
            isOneToOne: false
            referencedRelation: "kiosks"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "verification_sessions_matched_user_fkey"
            columns: ["matched_user"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      wallets: {
        Row: {
          balance: number
          currency: string
          family_member_id: string | null
          id: string
          updated_at: string
          user_id: string
        }
        Insert: {
          balance?: number
          currency?: string
          family_member_id?: string | null
          id?: string
          updated_at?: string
          user_id: string
        }
        Update: {
          balance?: number
          currency?: string
          family_member_id?: string | null
          id?: string
          updated_at?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "family_wallet_owner"
            columns: ["user_id", "family_member_id"]
            isOneToOne: false
            referencedRelation: "family_members"
            referencedColumns: ["user_id", "id"]
          },
          {
            foreignKeyName: "wallets_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      sfg_activate_profile: { Args: never; Returns: undefined }
      sfg_change_pin: {
        Args: { p_current_pin: string; p_new_pin: string; p_new_pin_confirm: string }
        Returns: undefined
      }
      sfg_charge_wallet: {
        Args: {
          p_amount: number
          p_auth_method: string
          p_idempotency_key: string
          p_kiosk_id: string
          p_merchant_name: string
          p_wallet_id: string
        }
        Returns: {
          balance_after: number
          transaction_id: string
        }[]
      }
      sfg_complete_dev_enrolment: { Args: never; Returns: undefined }
      sfg_complete_dev_family_enrolment: {
        Args: { p_family_member_id: string }
        Returns: undefined
      }
      sfg_create_family_member: {
        Args: {
          p_full_name: string
          p_ic: string
          p_idempotency_key: string
          p_relationship: string
        }
        Returns: string
      }
      sfg_registration_rate_limit: {
        Args: { p_identifier_hash: string }
        Returns: boolean
      }
      sfg_record_dev_family_capture: {
        Args: { p_family_member_id: string; p_pose: string }
        Returns: string[]
      }
      sfg_set_registration_pin: { Args: { p_pin: string }; Returns: undefined }
      sfg_start_enrolment: { Args: never; Returns: undefined }
      sfg_start_face_reenrolment: { Args: never; Returns: undefined }
      sfg_start_family_enrolment: {
        Args: { p_family_member_id: string }
        Returns: undefined
      }
      sfg_topup_wallet: {
        Args: { p_amount: number; p_idempotency_key: string; p_user_id: string }
        Returns: {
          balance_after: number
          transaction_id: string
        }[]
      }
      sfg_transfer_to_family: {
        Args: {
          p_amount: number
          p_family_member_id: string
          p_idempotency_key: string
          p_pin: string
          p_user_id: string
        }
        Returns: {
          family_balance: number
          main_balance: number
          reference: string
        }[]
      }
      sfg_user_topup_wallet: {
        Args: { p_amount: number; p_idempotency_key: string }
        Returns: {
          balance_after: number
          transaction_id: string
        }[]
      }
      sfg_user_transfer_to_family: {
        Args: {
          p_amount: number
          p_family_member_id: string
          p_idempotency_key: string
          p_pin: string
        }
        Returns: {
          family_balance: number
          main_balance: number
          reference: string
        }[]
      }
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {},
  },
} as const
