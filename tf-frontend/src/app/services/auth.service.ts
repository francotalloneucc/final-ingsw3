import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of, BehaviorSubject } from 'rxjs';
import { map, catchError } from 'rxjs/operators';
import { Router } from '@angular/router';
import { environment } from '../../environments/environment';

export interface User {
  id: number;
  email: string;
  nombre: string;
  role: 'candidato' | 'empresa' | 'admin';
  verified: boolean;
  profile_picture?: string;
  // Campos opcionales según el rol
  apellido?: string;
  genero?: 'masculino' | 'femenino' | 'otro';
  fecha_nacimiento?: string;
  cv_filename?: string;
  cv_analizado?: any; // NUEVO: Datos estructurados del CV
  descripcion?: string;
  created_at?: string;
}

export interface CandidatoRequest {
  email: string;
  password: string;
  nombre: string;
  apellido: string;
  genero: 'masculino' | 'femenino' | 'otro';
  fecha_nacimiento: string;
}

export interface EmpresaRequest {
  email: string;
  password: string;
  nombre: string;
  descripcion: string;
}

// Mantener para compatibilidad con código existente
export interface RegisterRequest {
  email: string;
  password: string;
  nombre: string;
  apellido: string;
  genero: 'masculino' | 'femenino' | 'otro';
  fecha_nacimiento: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private baseUrl = environment.apiUrl;

  // 🆕 AGREGADO: BehaviorSubject para estado de autenticación
  private isLoggedInSubject = new BehaviorSubject<boolean>(false);
  public isLoggedIn$ = this.isLoggedInSubject.asObservable();

  constructor(private http: HttpClient, private router: Router) {
    // Validar token al iniciar el servicio
    this.initializeAuthState();
  }

  // 🆕 NUEVO: Inicializar estado de autenticación al cargar el servicio
  private initializeAuthState(): void {
    const token = this.getToken();
    if (token) {
      // Si hay token, validar que sea válido
      this.validateToken().subscribe();
    } else {
      this.isLoggedInSubject.next(false);
    }
  }

  // 🆕 NUEVO: Validar si el token es válido consultando al backend
  validateToken(): Observable<boolean> {
    const token = this.getToken();
    
    if (!token) {
      this.isLoggedInSubject.next(false);
      return of(false);
    }

    return this.getCurrentUser().pipe(
      map(() => {
        // Si la petición es exitosa, el token es válido
        this.isLoggedInSubject.next(true);
        return true;
      }),
      catchError((error) => {
        // Si falla (403, 401, etc), el token no es válido
        console.warn('Token inválido o expirado, limpiando sesión');
        this.clearSession();
        return of(false);
      })
    );
  }

  // 🆕 NUEVO: Limpiar sesión sin redirigir
  private clearSession(): void {
    if (typeof window !== 'undefined' && window.localStorage) {
      localStorage.removeItem('token');
    }
    this.isLoggedInSubject.next(false);
  }

  // Registro de candidatos (simplificado - sin CV)
  registerCandidato(userData: CandidatoRequest, profilePicture?: File): Observable<User> {
    const formData = new FormData();
    formData.append('email', userData.email);
    formData.append('password', userData.password);
    formData.append('nombre', userData.nombre);
    formData.append('apellido', userData.apellido);
    formData.append('genero', userData.genero);
    formData.append('fecha_nacimiento', userData.fecha_nacimiento);
    if (profilePicture) formData.append('profile_picture', profilePicture);

    return this.http.post<User>(`${this.baseUrl}/register-candidato`, formData);
  }

  // Registro de empresas
  registerEmpresa(userData: EmpresaRequest, profilePicture?: File): Observable<User> {
    const formData = new FormData();
    formData.append('email', userData.email);
    formData.append('password', userData.password);
    formData.append('nombre', userData.nombre);
    formData.append('descripcion', userData.descripcion);
    if (profilePicture) formData.append('profile_picture', profilePicture);

    return this.http.post<User>(`${this.baseUrl}/register-empresa`, formData);
  }

  // Mantener método anterior para compatibilidad (simplificado)
  register(userData: RegisterRequest, profilePicture?: File): Observable<User> {
    return this.registerCandidato(userData, profilePicture);
  }

  // 🆕 ACTUALIZADO: Login con estado
  login(credentials: LoginRequest): Observable<AuthResponse> {
    return new Observable(observer => {
      this.http.post<AuthResponse>(`${this.baseUrl}/login`, credentials).subscribe({
        next: (response: AuthResponse) => {
          // Guardar token
          this.saveToken(response.access_token);
          
          // Actualizar estado de autenticación
          this.isLoggedInSubject.next(true);
          
          observer.next(response);
          observer.complete();
        },
        error: (error) => {
          observer.error(error);
        }
      });
    });
  }

  getCurrentUser(): Observable<User> {
    const token = this.getToken();
    const headers = {
      'Authorization': `Bearer ${token}`
    };
    
    return this.http.get<User>(`${this.baseUrl}/me`, { headers });
  }

  // Actualizar candidato
  updateCurrentCandidato(userData: Partial<CandidatoRequest>, cvFile?: File, profilePicture?: File): Observable<User> {
    const token = this.getToken();
    
    const formData = new FormData();
    if (userData.nombre) formData.append('nombre', userData.nombre);
    if (userData.apellido) formData.append('apellido', userData.apellido);
    if (userData.genero) formData.append('genero', userData.genero);
    if (userData.fecha_nacimiento) formData.append('fecha_nacimiento', userData.fecha_nacimiento);
    if (cvFile) formData.append('cv_file', cvFile);
    if (profilePicture) formData.append('profile_picture', profilePicture);

    return this.http.put<User>(`${this.baseUrl}/me/candidato`, formData, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
  }

  // Actualizar empresa
  updateCurrentEmpresa(userData: Partial<EmpresaRequest>, profilePicture?: File): Observable<User> {
    const token = this.getToken();
    
    const formData = new FormData();
    if (userData.nombre) formData.append('nombre', userData.nombre);
    if (userData.descripcion) formData.append('descripcion', userData.descripcion);
    if (profilePicture) formData.append('profile_picture', profilePicture);

    return this.http.put<User>(`${this.baseUrl}/me/empresa`, formData, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
  }

  // Mantener método anterior para compatibilidad
  updateCurrentUser(userData: Partial<RegisterRequest>, cvFile?: File, profilePicture?: File): Observable<User> {
    return this.updateCurrentCandidato(userData, cvFile, profilePicture);
  }

  // 🆕 ACTUALIZADO: SaveToken con estado
  saveToken(token: string): void {
    if (typeof window !== 'undefined' && window.localStorage) {
      localStorage.setItem('token', token);
      // Actualizar estado cuando se guarda token
      this.isLoggedInSubject.next(true);
    }
  }

  getToken(): string | null {
    if (typeof window !== 'undefined' && window.localStorage) {
      return localStorage.getItem('token');
    }
    return null;
  }

  // 🆕 ACTUALIZADO: isAuthenticated mejorado
  isAuthenticated(): boolean {
    const token = this.getToken();
    if (!token) {
      this.isLoggedInSubject.next(false);
      return false;
    }
    
    // Retornar true si hay token (la validación se hace en initializeAuthState)
    return true;
  }

  // 🆕 ACTUALIZADO: Logout con estado y redirección
  logout(): void {
    if (typeof window !== 'undefined' && window.localStorage) {
      localStorage.removeItem('token');
    }
    
    // Actualizar estado de autenticación
    this.isLoggedInSubject.next(false);
    
    // Redirigir al inicio
    this.router.navigate(['/']);
  }

  // Métodos para recruiters
  getMyRecruiters(): Observable<any> {
    const token = this.getToken();
    return this.http.get(`${this.baseUrl}/companies/my-recruiters`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
  }

  getRecruitingCompanies(): Observable<any> {
    const token = this.getToken();
    return this.http.get(`${this.baseUrl}/me/recruiting-for`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
  }

  addRecruiter(recruiterEmail: string): Observable<any> {
    const token = this.getToken();
    
    return this.http.post(
      `${this.baseUrl}/companies/add-recruiter?recruiter_email=${encodeURIComponent(recruiterEmail)}`, 
      {},
      {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );
  }

  removeRecruiter(recruiterEmail: string): Observable<any> {
    const token = this.getToken();

    return this.http.delete(
      `${this.baseUrl}/companies/remove-recruiter?recruiter_email=${encodeURIComponent(recruiterEmail)}`,
      {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );
  }

  resignFromCompany(companyId: number): Observable<any> {
    const token = this.getToken();

    return this.http.delete(
      `${this.baseUrl}/me/resign-from-company/${companyId}`,
      {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );
  }

  // Métodos para administradores
  
  // Obtener empresas pendientes de verificación
  getPendingCompanies(): Observable<User[]> {
    const token = this.getToken();
    return this.http.get<User[]>(`${this.baseUrl}/admin/companies/pending`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
  }

  // Verificar empresa (método simple)
  verifyCompany(companyEmail: string): Observable<any> {
    const token = this.getToken();
    
    return this.http.post(
      `${this.baseUrl}/admin/companies/verify?company_email=${encodeURIComponent(companyEmail)}`,
      {},
      {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );
  }

  // Obtener todos los candidatos
  getAllCandidates(skip: number = 0, limit: number = 100): Observable<User[]> {
    const token = this.getToken();
    return this.http.get<User[]>(`${this.baseUrl}/admin/candidates?skip=${skip}&limit=${limit}`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
  }

  // Obtener todos los usuarios (solo admins)
  getAllUsers(skip: number = 0, limit: number = 100): Observable<User[]> {
    const token = this.getToken();
    return this.http.get<User[]>(`${this.baseUrl}/admin/users?skip=${skip}&limit=${limit}`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
  }

  // ⭐ NUEVOS MÉTODOS para verificación de email - CORREGIDOS
  // Completar registro después de verificar email
  completeRegistration(email: string, verificationCode: string): Observable<any> {
    const formData = new FormData();
    formData.append('email', email);
    formData.append('verification_code', verificationCode);
    
    return this.http.post(`${this.baseUrl}/complete-registration`, formData);
  }

  // Verificar solo el código (sin completar registro)
  verifyEmail(email: string, code: string): Observable<any> {
    const formData = new FormData();
    formData.append('email', email);
    formData.append('code', code);
    
    return this.http.post(`${this.baseUrl}/verify-email`, formData);
  }

  // Reenviar código de verificación
  resendVerificationCode(email: string): Observable<any> {
    const formData = new FormData();
    formData.append('email', email);
    
    return this.http.post(`${this.baseUrl}/resend-verification`, formData);
  }
}