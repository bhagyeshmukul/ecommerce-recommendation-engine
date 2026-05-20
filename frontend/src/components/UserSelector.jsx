import { Search } from 'lucide-react';

export default function UserSelector({ users, selectedUser, onSelect, disabled }) {
  return (
    <label className="selector">
      <Search size={18} />
      <select value={selectedUser} onChange={(event) => onSelect(event.target.value)} disabled={disabled}>
        {users.map((userId) => (
          <option key={userId} value={userId}>
            {userId}
          </option>
        ))}
        <option value="COLD_START_USER">COLD_START_USER</option>
      </select>
    </label>
  );
}
