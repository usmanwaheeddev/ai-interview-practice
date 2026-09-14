import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { NotFoundPage } from "./components/NotFoundPage";
import { LoginPage } from "./features/auth/LoginPage";
import { RegisterCandidatePage } from "./features/auth/RegisterCandidatePage";
import { PrivacyNoticePage } from "./features/legal/PrivacyNoticePage";
import { CompletionPage } from "./features/interview/CompletionPage";
import { InterviewRoomPage } from "./features/interview/InterviewRoomPage";
import { PreflightPage } from "./features/interview/PreflightPage";
import { CreatePracticeInterviewPage } from "./features/practice/CreatePracticeInterviewPage";
import { CreateLanguageInterviewPage } from "./features/practice/CreateLanguageInterviewPage";
import { PracticeReportPage } from "./features/practice/PracticeReportPage";
import { InterviewHistoryPage } from "./features/practice/InterviewHistoryPage";
import { CodingQuestionListPage } from "./features/coding/CodingQuestionListPage";
import { CodingQuestionPage } from "./features/coding/CodingQuestionPage";
import { useAuth } from "./lib/auth";

function HomeRoute() {
  const { user, loading } = useAuth();

  if (loading) return <p>Loading…</p>;
  return <Navigate to={user ? "/practice/new" : "/login"} replace />;
}

export function App() {
  return (
    <Routes>
      <Route path="/mock-interviews" element={<ProtectedRoute><InterviewHistoryPage /></ProtectedRoute>} />
      <Route path="/" element={<HomeRoute />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterCandidatePage />} />
      <Route path="/privacy-notice" element={<PrivacyNoticePage />} />

      <Route path="/practice/new" element={<ProtectedRoute><CreatePracticeInterviewPage /></ProtectedRoute>} />
      <Route path="/practice/language/new" element={<ProtectedRoute><CreateLanguageInterviewPage /></ProtectedRoute>} />
      <Route path="/coding" element={<ProtectedRoute><CodingQuestionListPage /></ProtectedRoute>} />
      <Route path="/coding/:slug" element={<ProtectedRoute><CodingQuestionPage /></ProtectedRoute>} />
      <Route path="/mock-interviews/:interviewId/report" element={<ProtectedRoute><PracticeReportPage /></ProtectedRoute>} />
      <Route
        path="/mock-interviews/:interviewId/preflight"
        element={
          <ProtectedRoute>
            <PreflightPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/mock-interviews/:interviewId/room"
        element={
          <ProtectedRoute>
            <InterviewRoomPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/mock-interviews/:interviewId/complete"
        element={
          <ProtectedRoute>
            <CompletionPage />
          </ProtectedRoute>
        }
      />


      <Route path="/not-found" element={<NotFoundPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
