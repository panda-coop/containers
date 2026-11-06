# ubi10-keepalived

[keepalived](https://www.keepalived.org/) on Red Hat UBI 10 minimal: the `keepalived` RPM from
UBI 10 AppStream, Red Hat-signed, rebuilt on UBI updates.

The virtual IP for the edge pair `lb-01` / `lb-02`: VRRP keeps one address from `10.6.14.0/24`,
the network company employees reach from anywhere, on whichever LB has a ready Envoy. Only VRRP
is used; keepalived's LVS / IPVS side is not.

Built from github.com/panda-coop/containers. Not affiliated with or supported by Red Hat or the
upstream project.

| Item | Value |
|---|---|
| Image | `quay.io/panda-coop/ubi10-keepalived` |
| Upstream | `acassen/keepalived`, as packaged by Red Hat; version in `ARG VERSION` of the [Containerfile](Containerfile), the RPM release (`9.el10` today) follows UBI |
| Package | `keepalived`, pinned to `VERSION`, from `ubi-10-appstream-rpms`; every other repository is disabled for the install, so a subscribed build host's RHEL repositories cannot satisfy a dependency |
| Package check | `gpgcheck=1` against the Red Hat release key shipped in UBI (`ubi.repo`) |
| Base | `registry.access.redhat.com/ubi10/ubi-minimal`, pinned by digest |
| Dependencies | The RHEL build links net-snmp and libsystemd, so the RPM pulls in systemd, dbus and perl (through `net-snmp-agent-libs`); none of them runs. 168 MB |
| Architectures | `amd64`, `arm64` (UBI has both; CI publishes `amd64`) |
| User | `0:0`, see [Capabilities](#capabilities) |
| Licence | GPL-2.0-or-later, as the RPM's licence tag. The RPM ships no licence file, so upstream `COPYING` from the `v<VERSION>` tag (sha256-pinned) in `/licenses/keepalived/` |

UBI decides the version: Renovate reads the UBI 10 AppStream metadata (`datasource=rpm`), so a bump
PR appears only once UBI ships the new upstream version, and `rpm -q` checks it at build. A new RPM
release of the same version (a Red Hat fix) is picked up by the next rebuild, not by a PR.

## Tags

| Tag | Example | Moves |
|---|---|---|
| `x.y.z-<epoch>` | `2.2.8-<epoch>` | never |
| `x.y.z` | `2.2.8` | on a UBI rebuild |
| `x.y` | `2.2` | on a patch release |
| `x` | `2` | on a minor release |
| `latest` | | on every release |

See [ADR 0001](../docs/decisions/0001-image-tags-version-release-timestamp.md).

## Runtime

| Item | Value |
|---|---|
| Entrypoint | `keepalived --dont-fork --log-console --no-syslog --all-config --use-file=/etc/keepalived/keepalived.conf`; extra arguments are appended |
| Foreground | `--dont-fork`: the parent stays PID 1 and supervises its VRRP child; `SIGTERM` releases the VIP and exits |
| Logs | stdout / stderr (`--log-console`); `--no-syslog`, there is no `/dev/log` in the container |
| Configuration | None in the image; mount `/etc/keepalived/keepalived.conf` read-only. `--all-config` makes a missing file a startup error instead of an idle daemon |
| Reload | `SIGHUP` re-reads the configuration |
| Network | The host's: `Network=host`. The VIP is added to a host interface and VRRP runs on the host network |
| Port | None exposed: VRRP is IP protocol 112, not a port |
| Health-check tools | `curl` (already in ubi-minimal), for a `vrrp_script` against the local Envoy |

Check a configuration without starting VRRP:

```sh
podman run --rm --network host -v ./keepalived.conf:/etc/keepalived/keepalived.conf:ro,Z \
  quay.io/panda-coop/ubi10-keepalived:2.2.8 --config-test
```

`--config-test` exits non-zero on a syntax error, and also when an interface named in the file
does not exist in the network namespace, so run it with `--network host` on the LB itself.

### Capabilities

keepalived runs as root inside the container with every capability dropped except:

| Capability | Why |
|---|---|
| `NET_ADMIN` | Add and remove the VIP on the host interface, set the interface's ARP / multicast options |
| `NET_RAW` | The raw socket for VRRP (IP protocol 112) and gratuitous ARP after a failover |
| `NET_BROADCAST` | Multicast / broadcast advertisements; harmless with `unicast_peer`, kept for a multicast setup |
| `SETUID`, `SETGID` | Run each `vrrp_script` as `script_user` (`nobody`) instead of root; without them keepalived disables the script as insecure |
| `KILL` | Signal a timed-out `vrrp_script` running as `script_user`; without it the kill fails with EPERM, the check is never marked timed out and hung scripts pile up |

Root, rather than an unprivileged UID: keepalived is written to run as root and drops to
`script_user` itself for scripts, and the capabilities above, not the UID, are what bound it. With
`Network=host` the container is rootful: a rootless container cannot change the host's network
namespace.

## Example

Example addresses (not an allocation): VIP `10.6.14.10`, `lb-01` = `10.6.14.11`,
`lb-02` = `10.6.14.12`, interface `ens192`. Envoy's admin listener answers `GET /ready` on
`127.0.0.1:9901`; adjust to the deployed Envoy.

`/etc/keepalived/keepalived.conf` on `lb-01` (on `lb-02` swap the two addresses and the
`router_id`; both keep `state BACKUP` and the same priority, so `nopreempt` leaves the VIP where it
is when the other node comes back):

```text
global_defs {
    router_id lb-01
    enable_script_security
    script_user nobody
}

vrrp_script envoy_ready {
    script "/usr/bin/curl -fsS -o /dev/null --max-time 2 http://127.0.0.1:9901/ready"
    interval 2
    timeout 3
    fall 2
    rise 2
}

vrrp_instance edge {
    state BACKUP
    interface ens192
    virtual_router_id 14
    priority 100
    advert_int 1
    nopreempt
    unicast_src_ip 10.6.14.11
    unicast_peer {
        10.6.14.12
    }
    virtual_ipaddress {
        10.6.14.10/24 dev ens192
    }
    track_script {
        envoy_ready
    }
}
```

Unicast, not multicast to `224.0.0.18`: two nodes, a known peer, and no dependency on the switch
or hypervisor passing multicast. No `authentication` block: VRRP's `PASS` is cleartext and VRRPv3
drops authentication altogether; the firewall rule below, accepting VRRP from the peer only, is the
control. `virtual_router_id` must be unique per broadcast domain: 14 is an example, check what else
on `10.6.14.0/24` runs VRRP.

As a Quadlet, `/etc/containers/systemd/keepalived.container` (rootful):

```ini
[Container]
Image=quay.io/panda-coop/ubi10-keepalived:2.2.8
ContainerName=keepalived
Network=host
DropCapability=all
AddCapability=NET_ADMIN NET_BROADCAST NET_RAW SETUID SETGID KILL
Volume=/etc/keepalived/keepalived.conf:/etc/keepalived/keepalived.conf:ro,Z

[Service]
Restart=always
ExecReload=/usr/bin/podman kill --signal HUP keepalived

[Install]
WantedBy=multi-user.target
```

On the node without the VIP, Envoy binds the VIP only with `net.ipv4.ip_nonlocal_bind = 1` on
the host, or listens on `0.0.0.0`.

### Firewall

VRRP is its own IP protocol (112), not TCP or UDP; allow it between the two LBs only. With
firewalld on `lb-01`:

```sh
firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="10.6.14.12" protocol value="vrrp" accept'
firewall-cmd --reload
```

and the mirror rule (`source address="10.6.14.11"`) on `lb-02`. For a multicast setup the
destination is `224.0.0.18`.

### SELinux

The container runs as `container_t` (no `--privileged`, no `spc_t`).

| What | Verified |
|---|---|
| keepalived under `container_t`, enforcing, with the six capabilities: raw VRRP socket, VIP added through netlink, `vrrp_script` dropped to `nobody`, MASTER reached, clean stop on SIGTERM | Yes: RHEL 10.2, rootless Podman, an internal Podman network |
| No SELinux boolean changed for it; `virt_sandbox_use_all_caps` (`on` there, the RHEL default as far as known) lets `container_t` use the capabilities it is granted | Yes, on the same host |
| The same on the host network namespace (rootful, `Network=host`) on `lb-01` / `lb-02` | No: not run on the LBs. SELinux types do not change with the namespace, so no extra boolean is expected; if a failover misbehaves, check `ausearch -m avc -ts recent` before reaching for `spc_t` |

### Health

keepalived has no health endpoint, so the Quadlet has no `HealthCmd`. A crashed parent exits and
systemd restarts it (`Restart=always`); the VRRP child is respawned by the parent. Service health
is what VRRP tracks: `envoy_ready` failing twice puts the node in `FAULT`, the VIP moves to the
peer, and two passes bring it back as `BACKUP`. State changes are in the journal
(`journalctl -u keepalived`, `Entering MASTER STATE` / `Entering FAULT STATE`).

## Local build

```sh
task build IMAGE=keepalived     # localhost/ubi10-keepalived:dev
task run IMAGE=keepalived -- --version
task inspect IMAGE=keepalived
```

A version bump changes `ARG VERSION` and `ARG LICENSE_SHA256` only when upstream's `COPYING`
changes; a stale value fails the build.
