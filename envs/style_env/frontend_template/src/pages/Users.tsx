import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/Table";

const users = [
  {
    name: "Avery Brooks",
    email: "avery.brooks@northwind.io",
    role: "Admin",
    status: "Active",
    lastActive: "2 minutes ago",
  },
  {
    name: "Jordan Lee",
    email: "jordan.lee@northwind.io",
    role: "Manager",
    status: "Active",
    lastActive: "1 hour ago",
  },
  {
    name: "Priya Shah",
    email: "priya.shah@northwind.io",
    role: "Analyst",
    status: "Invited",
    lastActive: "Yesterday",
  },
  {
    name: "Rafael Costa",
    email: "rafael.costa@northwind.io",
    role: "Member",
    status: "Inactive",
    lastActive: "3 days ago",
  },
  {
    name: "Mei Chen",
    email: "mei.chen@northwind.io",
    role: "Member",
    status: "Active",
    lastActive: "Today, 9:18 AM",
  },
  {
    name: "Lucia Rossi",
    email: "lucia.rossi@northwind.io",
    role: "Manager",
    status: "Invited",
    lastActive: "Never",
  },
  {
    name: "Ethan Park",
    email: "ethan.park@northwind.io",
    role: "Analyst",
    status: "Active",
    lastActive: "4 hours ago",
  },
  {
    name: "Nina Alvarez",
    email: "nina.alvarez@northwind.io",
    role: "Member",
    status: "Inactive",
    lastActive: "8 days ago",
  },
];

const statusVariant = (status: string) => {
  if (status === "Active") {
    return "success";
  }
  if (status === "Invited") {
    return "default";
  }
  return "secondary";
};

export default function Users() {
  return (
    <div className="min-h-screen bg-gray-50 p-6 text-gray-900">
      <Card className="mx-auto max-w-6xl">
        <CardHeader className="gap-4 border-b border-gray-200">
          <div className="flex flex-col gap-2">
            <CardTitle className="text-xl">Users</CardTitle>
            <p className="text-sm text-gray-500">
              Manage access, roles, and activity for your organization.
            </p>
          </div>
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="w-full md:max-w-sm">
              <Input placeholder="Search users by name or email" />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="outline" size="sm">
                Role: All v
              </Button>
              <Button variant="outline" size="sm">
                Status: All v
              </Button>
              <Button size="sm">Add User</Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-6">
          <div className="rounded-md border border-gray-200">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last Active</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((user) => (
                  <TableRow key={user.email}>
                    <TableCell className="font-medium text-gray-900">
                      {user.name}
                    </TableCell>
                    <TableCell className="text-gray-600">
                      {user.email}
                    </TableCell>
                    <TableCell className="text-gray-700">{user.role}</TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(user.status)}>
                        {user.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-gray-600">
                      {user.lastActive}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className="mt-4 flex flex-col items-center justify-between gap-3 border-t border-gray-200 pt-4 text-sm text-gray-500 md:flex-row">
            <span>Showing 1-8 of 42 users</span>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm">
                Previous
              </Button>
              <Button variant="secondary" size="sm">
                1
              </Button>
              <Button variant="outline" size="sm">
                2
              </Button>
              <Button variant="outline" size="sm">
                3
              </Button>
              <Button variant="outline" size="sm">
                Next
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
