%if !0%{?version:1}
%define version 22.5.31
%endif

%if !0%{?release:1}
%define release 1
%endif

%define distnum %(/usr/lib/rpm/redhat/dist.sh --distnum)

Name:           python3-ecflow-openshift-agent
Version:        %{version}
Release:        %{release}%{dist}.fmi
Summary:        ecflow openshift agent
Group:          Applications/System
License:        MIT
URL:            http://www.fmi.fi
Source0: 	%{name}.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildRequires:  python3-devel
Requires:       python3-openshift-client
Provides:	python3dist(ecflow-openshift-agent)

AutoReqProv: no

%global debug_package %{nil}

%description
ecflow openshift agent is a tool for running ecflow jobs in openshift.
It automatically creates jobs from temnplates and monitors their progress.

%prep
%setup -q -n "ecflow-openshift-agent"

%build
%py3_build

%install
rm -rf $RPM_BUILD_ROOT

%py3_install

mkdir -p %{buildroot}/%{_bindir}
cp -a run-agent.py %{buildroot}/%{_bindir}/

%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root,0755)
%{python3_sitelib}/ecflow_openshift_agent*
%{_bindir}/run-agent.py

%changelog
* Tue May 31 2022 Mikko Partio <mikko.partio@fmi.fi> - 22.5.31-1.fmi
- New release
