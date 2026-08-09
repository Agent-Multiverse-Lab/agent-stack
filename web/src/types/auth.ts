export interface RegisterRequest {
  email: string
  password: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface UserResponse {
  id: number
  uid: string
  email: string
  is_active: boolean
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: UserResponse
}
