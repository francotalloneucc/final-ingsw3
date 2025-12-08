import { TestBed } from '@angular/core/testing';
import { HttpClient, HttpClientModule } from '@angular/common/http';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { Router } from '@angular/router';
import { AuthService, User, CandidatoRequest, EmpresaRequest, LoginRequest, AuthResponse } from './auth.service';

describe('AuthService', () => {
  let service: AuthService;
  let httpMock: HttpTestingController;
  let routerSpy: jasmine.SpyObj<Router>;

  const mockUser: User = {
    id: 1,
    email: 'test@example.com',
    nombre: 'Test User',
    role: 'candidato',
    verified: true,
    apellido: 'Apellido',
    genero: 'masculino',
    fecha_nacimiento: '1990-01-01',
    cv_filename: 'test-cv.pdf',
    cv_analizado: { skills: ['Python'] }
  };

  const mockAuthResponse: AuthResponse = {
    access_token: 'test-token-123',
    token_type: 'bearer'
  };

  beforeEach(() => {
    const routerSpyObj = jasmine.createSpyObj('Router', ['navigate']);

    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [
        AuthService,
        { provide: Router, useValue: routerSpyObj }
      ]
    });

    service = TestBed.inject(AuthService);
    httpMock = TestBed.inject(HttpTestingController);
    routerSpy = TestBed.inject(Router) as jasmine.SpyObj<Router>;

    // Clear localStorage before each test
    localStorage.clear();
  });

  afterEach(() => {
    httpMock.verify();
    localStorage.clear();
  });

  describe('Token Management', () => {
    it('should save and retrieve token', () => {
      const token = 'test-token-123';
      service.saveToken(token);
      
      expect(service.getToken()).toBe(token);
      expect(localStorage.getItem('token')).toBe(token);
    });

    it('should return null when no token exists', () => {
      expect(service.getToken()).toBeNull();
    });

    it('should clear session on logout', () => {
      service.saveToken('test-token');
      service.logout();
      
      expect(service.getToken()).toBeNull();
      expect(routerSpy.navigate).toHaveBeenCalledWith(['/']);
    });
  });

  describe('Authentication State', () => {
    it('should initialize with logged out state', () => {
      service.isLoggedIn$.subscribe(isLoggedIn => {
        expect(isLoggedIn).toBeFalse();
      });
    });

    it('should update state when token is saved', () => {
      let isLoggedIn = false;
      service.isLoggedIn$.subscribe(state => isLoggedIn = state);
      
      service.saveToken('test-token');
      expect(isLoggedIn).toBeTrue();
    });

    it('should validate token on initialization', () => {
      localStorage.setItem('token', 'test-token');

      // Create new service instance to trigger initialization
      const httpClient = TestBed.inject(HttpClient);
      const newService = new AuthService(httpClient, routerSpy);

      const req = httpMock.expectOne('http://localhost:8000/api/v1/me');
      expect(req.request.method).toBe('GET');
      req.flush(mockUser);
    });

    it('should handle invalid token during validation', () => {
      localStorage.setItem('token', 'invalid-token');

      const httpClient = TestBed.inject(HttpClient);
      const newService = new AuthService(httpClient, routerSpy);

      const req = httpMock.expectOne('http://localhost:8000/api/v1/me');
      req.error(new ErrorEvent('Unauthorized'), { status: 401 });

      expect(localStorage.getItem('token')).toBeNull();
    });
  });

  describe('Registration', () => {
    it('should register candidato successfully', () => {
      const candidatoData: CandidatoRequest = {
        email: 'candidate@example.com',
        password: 'password123',
        nombre: 'Juan',
        apellido: 'Pérez',
        genero: 'masculino',
        fecha_nacimiento: '1990-01-01'
      };
      const mockFile = new File(['cv content'], 'cv.pdf', { type: 'application/pdf' });

      service.registerCandidato(candidatoData, mockFile).subscribe(user => {
        expect(user).toEqual(mockUser);
      });

      const req = httpMock.expectOne('http://localhost:8000/api/v1/register-candidato');
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toBeInstanceOf(FormData);
      req.flush(mockUser);
    });

    it('should register empresa successfully', () => {
      const empresaData: EmpresaRequest = {
        email: 'company@example.com',
        password: 'password123',
        nombre: 'Tech Company',
        descripcion: 'Leading tech company'
      };

      const empresaUser = { ...mockUser, role: 'empresa' as const };

      service.registerEmpresa(empresaData).subscribe(user => {
        expect(user).toEqual(empresaUser);
      });

      const req = httpMock.expectOne('http://localhost:8000/api/v1/register-empresa');
      expect(req.request.method).toBe('POST');
      req.flush(empresaUser);
    });

    it('should complete registration after email verification', () => {
      const email = 'test@example.com';
      const code = '123456';

      service.completeRegistration(email, code).subscribe(response => {
        expect(response).toEqual(mockUser);
      });

      const req = httpMock.expectOne('http://localhost:8000/api/v1/complete-registration');
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toBeInstanceOf(FormData);
      req.flush(mockUser);
    });
  });

  describe('Login', () => {
    it('should login successfully', () => {
      const loginData: LoginRequest = {
        email: 'test@example.com',
        password: 'password123'
      };

      let authState = false;
      service.isLoggedIn$.subscribe(state => authState = state);

      service.login(loginData).subscribe(response => {
        expect(response).toEqual(mockAuthResponse);
        expect(authState).toBeTrue();
        expect(localStorage.getItem('token')).toBe('test-token-123');
      });

      const req = httpMock.expectOne('http://localhost:8000/api/v1/login');
      expect(req.request.method).toBe('POST');
      req.flush(mockAuthResponse);
    });

    it('should handle login error', () => {
      const loginData: LoginRequest = {
        email: 'test@example.com',
        password: 'wrong-password'
      };

      service.login(loginData).subscribe({
        next: () => fail('Should have failed'),
        error: (error) => {
          expect(error).toBeDefined();
        }
      });

      const req = httpMock.expectOne('http://localhost:8000/api/v1/login');
      req.error(new ErrorEvent('Unauthorized'), { status: 401 });
    });
  });

  describe('User Profile', () => {
    beforeEach(() => {
      localStorage.setItem('token', 'test-token');
    });

    it('should get current user', () => {
      service.getCurrentUser().subscribe(user => {
        expect(user).toEqual(mockUser);
      });

      const req = httpMock.expectOne('http://localhost:8000/api/v1/me');
      expect(req.request.headers.get('Authorization')).toBe('Bearer test-token');
      req.flush(mockUser);
    });

    it('should update candidato profile', () => {
      const updateData = { nombre: 'Updated Name' };
      const mockFile = new File(['new cv'], 'new-cv.pdf', { type: 'application/pdf' });

      service.updateCurrentCandidato(updateData, mockFile).subscribe(user => {
        expect(user).toEqual(mockUser);
      });

      const req = httpMock.expectOne('http://localhost:8000/api/v1/me/candidato');
      expect(req.request.method).toBe('PUT');
      expect(req.request.headers.get('Authorization')).toBe('Bearer test-token');
      req.flush(mockUser);
    });

    it('should update empresa profile', () => {
      const updateData = { nombre: 'Updated Company' };

      service.updateCurrentEmpresa(updateData).subscribe(user => {
        expect(user).toEqual(mockUser);
      });

      const req = httpMock.expectOne('http://localhost:8000/api/v1/me/empresa');
      expect(req.request.method).toBe('PUT');
      req.flush(mockUser);
    });
  });

  describe('Email Verification', () => {
    it('should verify email code', () => {
      const email = 'test@example.com';
      const code = '123456';

      service.verifyEmail(email, code).subscribe(response => {
        expect(response.success).toBeTrue();
      });

      const req = httpMock.expectOne('http://localhost:8000/api/v1/verify-email');
      expect(req.request.method).toBe('POST');
      req.flush({ success: true, message: 'Code verified' });
    });

    it('should resend verification code', () => {
      const email = 'test@example.com';

      service.resendVerificationCode(email).subscribe(response => {
        expect(response.success).toBeTrue();
      });

      const req = httpMock.expectOne('http://localhost:8000/api/v1/resend-verification');
      expect(req.request.method).toBe('POST');
      req.flush({ success: true, message: 'Code resent' });
    });
  });

  describe('Recruiter Management', () => {
    beforeEach(() => {
      localStorage.setItem('token', 'test-token');
    });

    it('should get my recruiters', () => {
      const mockRecruiters = {
        company: 'Test Company',
        recruiters: [{ id: 1, name: 'Recruiter 1' }],
        total: 1
      };

      service.getMyRecruiters().subscribe(recruiters => {
        expect(recruiters).toEqual(mockRecruiters);
      });

      const req = httpMock.expectOne('http://localhost:8000/api/v1/companies/my-recruiters');
      req.flush(mockRecruiters);
    });

    it('should get recruiting companies', () => {
      const mockCompanies = {
        recruiter: 'John Doe',
        companies: [{ id: 1, name: 'Company 1' }],
        total: 1
      };

      service.getRecruitingCompanies().subscribe(companies => {
        expect(companies).toEqual(mockCompanies);
      });

      const req = httpMock.expectOne('http://localhost:8000/api/v1/me/recruiting-for');
      req.flush(mockCompanies);
    });

    it('should add recruiter', () => {
      const recruiterEmail = 'recruiter@example.com';

      service.addRecruiter(recruiterEmail).subscribe(response => {
        expect(response.message).toContain('agregado exitosamente');
      });

      const expectedUrl = `http://localhost:8000/api/v1/companies/add-recruiter?recruiter_email=${encodeURIComponent(recruiterEmail)}`;
      const req = httpMock.expectOne(expectedUrl);
      expect(req.request.method).toBe('POST');
      req.flush({ message: 'Recruiter agregado exitosamente' });
    });

    it('should remove recruiter', () => {
      const recruiterEmail = 'recruiter@example.com';

      service.removeRecruiter(recruiterEmail).subscribe(response => {
        expect(response.message).toContain('removido exitosamente');
      });

      const expectedUrl = `http://localhost:8000/api/v1/companies/remove-recruiter?recruiter_email=${encodeURIComponent(recruiterEmail)}`;
      const req = httpMock.expectOne(expectedUrl);
      expect(req.request.method).toBe('DELETE');
      req.flush({ message: 'Recruiter removido exitosamente' });
    });
  });

  describe('Admin Operations', () => {
    beforeEach(() => {
      localStorage.setItem('token', 'admin-token');
    });

    it('should get pending companies', () => {
      const mockPendingCompanies = [
        { ...mockUser, role: 'empresa' as const, verified: false }
      ];

      service.getPendingCompanies().subscribe(companies => {
        expect(companies).toEqual(mockPendingCompanies);
      });

      const req = httpMock.expectOne('http://localhost:8000/api/v1/admin/companies/pending');
      req.flush(mockPendingCompanies);
    });

    it('should verify company', () => {
      const companyEmail = 'company@example.com';

      service.verifyCompany(companyEmail).subscribe(response => {
        expect(response.message).toContain('verificada exitosamente');
      });

      const expectedUrl = `http://localhost:8000/api/v1/admin/companies/verify?company_email=${encodeURIComponent(companyEmail)}`;
      const req = httpMock.expectOne(expectedUrl);
      expect(req.request.method).toBe('POST');
      req.flush({ message: 'Empresa verificada exitosamente' });
    });

    it('should get all candidates', () => {
      const mockCandidates = [mockUser];

      service.getAllCandidates(0, 10).subscribe(candidates => {
        expect(candidates).toEqual(mockCandidates);
      });

      const req = httpMock.expectOne('http://localhost:8000/api/v1/admin/candidates?skip=0&limit=10');
      req.flush(mockCandidates);
    });

    it('should get all users', () => {
      const mockUsers = [mockUser];

      service.getAllUsers(0, 10).subscribe(users => {
        expect(users).toEqual(mockUsers);
      });

      const req = httpMock.expectOne('http://localhost:8000/api/v1/admin/users?skip=0&limit=10');
      req.flush(mockUsers);
    });
  });

  describe('Edge Cases and Error Handling', () => {
    it('should handle missing localStorage', () => {
      // Mock localStorage to be undefined
      spyOn(Storage.prototype, 'getItem').and.returnValue(null);
      spyOn(Storage.prototype, 'setItem');

      expect(service.getToken()).toBeNull();
      
      service.saveToken('test-token');
      // Should not throw error even if localStorage is not available
    });

    it('should handle expired token gracefully', () => {
      localStorage.setItem('token', 'expired-token');

      service.validateToken().subscribe(isValid => {
        expect(isValid).toBeFalse();
      });

      const req = httpMock.expectOne('http://localhost:8000/api/v1/me');
      req.error(new ErrorEvent('Token expired'), { status: 401 });
    });
  });

  describe('Authentication Flow Integration', () => {
    it('should complete full authentication flow', () => {
      let authState = false;
      service.isLoggedIn$.subscribe(state => authState = state);

      // Initial state should be false
      expect(authState).toBeFalse();

      // Login
      const loginData: LoginRequest = {
        email: 'test@example.com',
        password: 'password123'
      };

      service.login(loginData).subscribe();
      
      const loginReq = httpMock.expectOne('http://localhost:8000/api/v1/login');
      loginReq.flush(mockAuthResponse);

      // Auth state should now be true
      expect(authState).toBeTrue();
      expect(localStorage.getItem('token')).toBe('test-token-123');

      // Logout
      service.logout();
      expect(authState).toBeFalse();
      expect(localStorage.getItem('token')).toBeNull();
      expect(routerSpy.navigate).toHaveBeenCalledWith(['/']);
    });
  });
});