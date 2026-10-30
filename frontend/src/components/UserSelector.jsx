/** Keep the search input separate from the selected customer to avoid half-IDs. */
export default function UserSelector({
  users,
  query,
  onQuery,
  selectedUser,
  onSelect,
  disabled,
}) {
  const filtered = users.filter((user) => user.includes(query));
  return (
    <div className="customer-controls">
      <label>
        <span>Find a customer</span>
        <input
          type="search"
          placeholder="Search customer ID"
          value={query}
          onChange={(event) => onQuery(event.target.value)}
        />
      </label>
      <label>
        <span>Purchase history</span>
        <select
          aria-label="Customer"
          value={selectedUser}
          onChange={(event) => onSelect(event.target.value)}
          disabled={disabled}
        >
          <option value="NEW_CUSTOMER">New customer · no history</option>
          {!filtered.includes(selectedUser) &&
            selectedUser !== "NEW_CUSTOMER" && (
              <option value={selectedUser}>{selectedUser}</option>
            )}
          {filtered.map((user) => (
            <option key={user} value={user}>
              Customer {user}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
