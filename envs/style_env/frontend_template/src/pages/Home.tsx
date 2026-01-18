import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";

export default function Home() {
  return (
    <div className="min-h-screen bg-slate-50">
      {/* Navbar */}
      <nav className="border-b border-slate-200 bg-white shadow-sm">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <div className="flex items-center space-x-8">
            <span className="text-xl font-bold text-indigo-600">Lumina</span>
            <div className="hidden space-x-6 md:flex">
              <a
                href="#"
                className="text-sm font-medium text-slate-600 hover:text-indigo-600"
              >
                Features
              </a>
              <a
                href="#"
                className="text-sm font-medium text-slate-600 hover:text-indigo-600"
              >
                Pricing
              </a>
              <a
                href="#"
                className="text-sm font-medium text-slate-600 hover:text-indigo-600"
              >
                About
              </a>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <Button
              variant="ghost"
              className="text-slate-600 hover:bg-slate-50 hover:text-indigo-600"
            >
              Log in
            </Button>
            <Button className="bg-indigo-600 hover:bg-indigo-700">
              Sign up
            </Button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8 lg:py-24">
        <div className="text-center">
          <h1 className="text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl lg:text-6xl">
            Simplify your{" "}
            <span className="text-indigo-600">daily workflow</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-slate-600">
            Lumina brings all your tasks, notes, and team collaboration into one
            beautiful, easy-to-use platform.
          </p>
          <div className="mt-10 flex justify-center gap-4">
            <Button
              size="lg"
              className="rounded-full bg-indigo-600 px-8 hover:bg-indigo-700"
            >
              Get Started for Free
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="rounded-full border-slate-300 text-slate-700 hover:bg-slate-50 hover:text-indigo-600"
            >
              Watch Demo
            </Button>
          </div>
        </div>
      </div>

      {/* Feature Cards */}
      <div className="mx-auto max-w-7xl px-4 pb-24 sm:px-6 lg:px-8">
        <div className="grid gap-8 md:grid-cols-3">
          <Card className="rounded-xl border-slate-200 shadow-md transition-shadow hover:shadow-lg">
            <CardHeader>
              <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-lg bg-indigo-100 text-indigo-600">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  className="h-6 w-6"
                >
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                </svg>
              </div>
              <CardTitle className="text-xl text-slate-900">
                Secure by Design
              </CardTitle>
              <CardDescription className="text-slate-500">
                Enterprise-grade encryption keeps your data safe and private.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-slate-600">
                We utilize state-of-the-art security protocols to ensure your
                information never falls into the wrong hands.
              </p>
            </CardContent>
          </Card>

          <Card className="rounded-xl border-slate-200 shadow-md transition-shadow hover:shadow-lg">
            <CardHeader>
              <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-lg bg-emerald-100 text-emerald-600">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  className="h-6 w-6"
                >
                  <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
                </svg>
              </div>
              <CardTitle className="text-xl text-slate-900">
                Lightning Fast
              </CardTitle>
              <CardDescription className="text-slate-500">
                Optimized performance for a seamless user experience.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-slate-600">
                Load times under 100ms. Lumina is built for speed, so you never
                have to wait for your tools to catch up.
              </p>
            </CardContent>
          </Card>

          <Card className="rounded-xl border-slate-200 shadow-md transition-shadow hover:shadow-lg">
            <CardHeader>
              <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-lg bg-indigo-100 text-indigo-600">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  className="h-6 w-6"
                >
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
              </div>
              <CardTitle className="text-xl text-slate-900">
                Team Collaboration
              </CardTitle>
              <CardDescription className="text-slate-500">
                Work together in real-time, no matter where you are.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-slate-600">
                Share projects, comment on tasks, and see updates instantly
                across all devices.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Newsletter Section */}
      <div className="bg-white py-16">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="rounded-2xl bg-indigo-600 px-6 py-12 md:px-12 lg:flex lg:items-center lg:justify-between lg:py-16">
            <div>
              <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
                Ready to dive in?
              </h2>
              <p className="mt-3 max-w-3xl text-lg text-indigo-100">
                Join over 10,000 users transforming their productivity today.
              </p>
            </div>
            <div className="mt-8 flex w-full max-w-md gap-x-4 lg:ml-8 lg:mt-0">
              <Input
                type="email"
                placeholder="Enter your email"
                className="rounded-full border-transparent bg-white/10 px-5 text-white placeholder:text-indigo-200 focus-visible:ring-white/50"
              />
              <Button
                variant="secondary"
                className="rounded-full px-6 font-semibold hover:bg-white/90"
              >
                Subscribe
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="bg-slate-50 py-12">
        <div className="mx-auto max-w-7xl px-4 text-center sm:px-6 lg:px-8">
          <p className="text-sm text-slate-500">
            &copy; 2024 Lumina Inc. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
}
