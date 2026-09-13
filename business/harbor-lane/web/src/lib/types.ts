export interface Firm {
  id: string;
  slug: string;
  legal_name: string;
  trading_name: string;
  billing_email: string;
  support_email: string;
  phone: string;
  website: string;
  address_line1: string;
  city: string;
  postcode: string;
}

export interface Customer {
  id: string;
  name: string;
  industry: string | null;
  city: string | null;
  primary_contact_name: string | null;
  primary_contact_email: string | null;
}

export interface Lead {
  id: string;
  company_name: string;
  contact_name: string;
  contact_email: string;
  status: string;
  estimated_value_gbp: number | null;
  source: string | null;
}

export interface Project {
  id: string;
  name: string;
  project_type: string;
  status: string;
  budget_gbp: number | null;
  monthly_retainer_gbp: number | null;
  customer_id: string;
  customers?: { name: string };
}

export interface Invoice {
  id: string;
  invoice_number: string;
  status: string;
  issue_date: string;
  due_date: string;
  subtotal_gbp: number;
  vat_gbp: number;
  total_gbp: number;
  amount_paid_gbp: number;
  customer_id: string;
  customers?: { name: string };
}

export interface Message {
  id: string;
  subject: string;
  body: string;
  is_from_client: boolean;
  is_read: boolean;
  created_at: string;
  customer_id: string;
}

export interface ChartAccount {
  id: string;
  code: string;
  name: string;
  account_type: string;
  tax_type: string | null;
  xero_account_id: string | null;
}
